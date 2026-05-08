```react
import React, { useState, useEffect, useMemo } from 'react';
import { initializeApp } from 'firebase/app';
import { 
  getAuth, 
  signInAnonymously, 
  signInWithCustomToken, 
  onAuthStateChanged 
} from 'firebase/auth';
import { 
  getFirestore, 
  doc, 
  setDoc, 
  getDoc, 
  onSnapshot, 
  collection, 
  addDoc, 
  serverTimestamp,
  updateDoc,
  increment,
  query,
  where,
  getDocs
} from 'firebase/firestore';
import { 
  ShieldCheck, RefreshCw, Users, Send, X, ShieldAlert, 
  ArrowRightLeft, LogIn, UserPlus, LogOut, Lock, User as UserIcon, Crown, Key, LayoutDashboard
} from 'lucide-react';

const firebaseConfig = JSON.parse(__firebase_config);
const app = initializeApp(firebaseConfig);
const auth = getAuth(app);
const db = getFirestore(app);
const appId = typeof __app_id !== 'undefined' ? __app_id : 'horizon-v3-stable';

// OWNER CONFIGURATION
const OWNER_USERNAME = "fanu_805";
const OWNER_ACCESS_KEY = "71675360";

const App = () => {
  const [fbUser, setFbUser] = useState(null); // Firebase Auth State
  const [appUser, setAppUser] = useState(null); // App Logic State
  const [loading, setLoading] = useState(true);
  const [accountData, setAccountData] = useState(null);
  const [transactions, setTransactions] = useState([]);
  const [allUsers, setAllUsers] = useState([]);
  const [activeTab, setActiveTab] = useState('dashboard');
  const [isSidebarOpen, setSidebarOpen] = useState(true);
  
  const [isLoginView, setIsLoginView] = useState(true);
  const [authForm, setAuthForm] = useState({ username: '', password: '' });
  const [authError, setAuthError] = useState('');
  const [isAuthProcessing, setIsAuthProcessing] = useState(false);

  const [recipientId, setRecipientId] = useState('');
  const [amount, setAmount] = useState('');
  const [isProcessing, setIsProcessing] = useState(false);

  // 1. Initialize Firebase Authentication First (RULE 3)
  useEffect(() => {
    const initAuth = async () => {
      try {
        if (typeof __initial_auth_token !== 'undefined' && __initial_auth_token) {
          await signInWithCustomToken(auth, __initial_auth_token);
        } else {
          await signInAnonymously(auth);
        }
      } catch (err) {
        console.error("Auth init error", err);
      }
    };
    initAuth();
    
    const unsubscribe = onAuthStateChanged(auth, (user) => {
      setFbUser(user);
      // Check for locally saved app session
      const saved = localStorage.getItem(`horizon_session_${appId}`);
      if (saved) setAppUser(JSON.parse(saved));
      setLoading(false);
    });
    return () => unsubscribe();
  }, []);

  // 2. Data Syncing (Only after Auth and App Login)
  useEffect(() => {
    if (!fbUser || !appUser) return;

    const accountRef = doc(db, 'artifacts', appId, 'public', 'data', 'accounts', appUser.uid);
    const unsubAccount = onSnapshot(accountRef, (snap) => {
      if (snap.exists()) {
        const data = snap.data();
        // Self-healing for Owner Admin status
        if (data.username === OWNER_USERNAME && !data.isAdmin) {
          updateDoc(accountRef, { isAdmin: true });
        }
        setAccountData(data);
      }
    }, (err) => console.error("Account sync error", err));

    const allRef = collection(db, 'artifacts', appId, 'public', 'data', 'accounts');
    const unsubAll = onSnapshot(allRef, (snap) => {
      setAllUsers(snap.docs.map(d => d.data()));
    }, (err) => console.error("Directory sync error", err));

    const txRef = collection(db, 'artifacts', appId, 'users', appUser.uid, 'transactions');
    const unsubTx = onSnapshot(txRef, (snap) => {
      const list = snap.docs.map(d => ({ id: d.id, ...d.data() }));
      setTransactions(list.sort((a, b) => (b.timestamp?.seconds || 0) - (a.timestamp?.seconds || 0)));
    }, (err) => console.error("TX sync error", err));

    return () => {
      unsubAccount();
      unsubAll();
      unsubTx();
    };
  }, [fbUser, appUser]);

  const handleAuth = async (e) => {
    e.preventDefault();
    if (!fbUser) return setAuthError("Waiting for secure connection...");
    
    setAuthError('');
    setIsAuthProcessing(true);
    const inputUsername = authForm.username.toLowerCase().trim();

    try {
      // Owner Key Validation
      if (inputUsername === OWNER_USERNAME && authForm.password !== OWNER_ACCESS_KEY) {
        throw new Error("Invalid Owner Access Key.");
      }

      const q = query(collection(db, 'artifacts', appId, 'public', 'data', 'accounts'), where("username", "==", inputUsername));
      const querySnapshot = await getDocs(q);

      if (isLoginView) {
        // LOGIN LOGIC
        if (querySnapshot.empty) throw new Error("Account not found.");
        const foundData = querySnapshot.docs[0].data();
        if (foundData.password !== authForm.password) throw new Error("Incorrect access key.");
        
        const session = { uid: foundData.uid, username: inputUsername };
        localStorage.setItem(`horizon_session_${appId}`, JSON.stringify(session));
        setAppUser(session);
      } else {
        // REGISTER LOGIC
        if (!querySnapshot.empty) throw new Error("Username already registered.");
        
        const newUid = crypto.randomUUID();
        const isOwner = inputUsername === OWNER_USERNAME;
        const newAccount = {
          uid: newUid,
          username: inputUsername,
          password: authForm.password,
          balance: isOwner ? 1000000 : 1000,
          isAdmin: isOwner,
          createdAt: new Date().toISOString()
        };

        await setDoc(doc(db, 'artifacts', appId, 'public', 'data', 'accounts', newUid), newAccount);
        const session = { uid: newUid, username: inputUsername };
        localStorage.setItem(`horizon_session_${appId}`, JSON.stringify(session));
        setAppUser(session);
      }
    } catch (err) {
      setAuthError(err.message || "Operation failed.");
    } finally {
      setIsAuthProcessing(false);
    }
  };

  const logout = () => {
    localStorage.removeItem(`horizon_session_${appId}`);
    setAppUser(null);
    setAccountData(null);
  };

  const handleTransfer = async (e) => {
    e.preventDefault();
    const val = parseFloat(amount);
    if (!val || val <= 0 || val > (accountData?.balance || 0)) return;
    setIsProcessing(true);
    try {
      const receiverRef = doc(db, 'artifacts', appId, 'public', 'data', 'accounts', recipientId);
      const receiverSnap = await getDoc(receiverRef);
      if (!receiverSnap.exists()) throw new Error("Receiver does not exist.");

      const receiverData = receiverSnap.data();
      await updateDoc(doc(db, 'artifacts', appId, 'public', 'data', 'accounts', appUser.uid), { balance: increment(-val) });
      await updateDoc(receiverRef, { balance: increment(val) });

      await addDoc(collection(db, 'artifacts', appId, 'users', appUser.uid, 'transactions'), {
        merchant: `Transfer to @${receiverData.username}`,
        amount: -val,
        category: 'Outbound',
        timestamp: serverTimestamp()
      });
      await addDoc(collection(db, 'artifacts', appId, 'users', recipientId, 'transactions'), {
        merchant: `Received from @${accountData.username}`,
        amount: val,
        category: 'Inbound',
        timestamp: serverTimestamp()
      });
      setAmount('');
      setRecipientId('');
    } catch (err) {
      alert(err.message);
    } finally { setIsProcessing(false); }
  };

  if (loading) return (
    <div className="h-screen bg-slate-950 flex flex-col items-center justify-center gap-4">
      <RefreshCw className="animate-spin text-indigo-500" size={32} />
      <span className="text-slate-500 font-bold tracking-widest text-xs">ESTABLISHING ENCRYPTED LINK</span>
    </div>
  );

  if (!appUser) return (
    <div className="min-h-screen bg-slate-950 flex items-center justify-center p-6 relative">
      <div className="absolute top-0 left-1/2 -translate-x-1/2 w-full max-w-lg h-96 bg-indigo-500/10 blur-[120px] rounded-full pointer-events-none"></div>
      <div className="w-full max-w-md bg-slate-900 border border-white/5 rounded-[2.5rem] p-10 shadow-2xl relative z-10">
        <div className="flex flex-col items-center mb-10 text-center">
          <div className="w-20 h-20 bg-indigo-600 rounded-[1.8rem] flex items-center justify-center text-white mb-6 shadow-xl">
            <ShieldCheck size={40} />
          </div>
          <h1 className="text-3xl font-black text-white tracking-tighter uppercase italic">Horizon<span className="text-indigo-500">Bank</span></h1>
        </div>

        <form onSubmit={handleAuth} className="space-y-6">
          <div className="space-y-2">
            <label className="text-[10px] font-black text-slate-500 uppercase tracking-widest ml-1">Username</label>
            <div className="relative">
              <UserIcon className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-500" size={18} />
              <input required className="w-full bg-slate-800 border-none rounded-2xl py-4 pl-12 pr-4 text-white placeholder:text-slate-600" placeholder="e.g. Fanu_805" value={authForm.username} onChange={e => setAuthForm({...authForm, username: e.target.value})} />
            </div>
          </div>
          <div className="space-y-2">
            <label className="text-[10px] font-black text-slate-500 uppercase tracking-widest ml-1">Access Key</label>
            <div className="relative">
              <Key className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-500" size={18} />
              <input required type="password" className="w-full bg-slate-800 border-none rounded-2xl py-4 pl-12 pr-4 text-white placeholder:text-slate-600" placeholder="••••••••" value={authForm.password} onChange={e => setAuthForm({...authForm, password: e.target.value})} />
            </div>
          </div>

          {authError && <div className="p-4 bg-rose-500/10 text-rose-500 text-[11px] rounded-xl font-bold border border-rose-500/20 text-center">{authError}</div>}

          <button disabled={isAuthProcessing} className="w-full bg-white text-slate-950 font-black py-4 rounded-2xl transition-all hover:bg-indigo-50 active:scale-95 disabled:opacity-50">
            {isAuthProcessing ? 'PROCESSING...' : (isLoginView ? 'LOG IN TO VAULT' : 'CREATE ACCOUNT')}
          </button>
        </form>

        <button onClick={() => { setIsLoginView(!isLoginView); setAuthError(''); }} className="w-full mt-6 text-[10px] text-slate-500 hover:text-white font-black uppercase tracking-widest">
          {isLoginView ? "Don't have an account? Sign Up" : "Already registered? Sign In"}
        </button>
      </div>
    </div>
  );

  if (!accountData) return (
    <div className="h-screen bg-slate-950 flex flex-col items-center justify-center gap-4">
      <RefreshCw className="animate-spin text-indigo-500" size={32} />
      <span className="text-slate-500 font-bold tracking-widest text-xs">SYNCHRONIZING LEDGER</span>
    </div>
  );

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex overflow-hidden">
      <aside className={`fixed inset-y-0 left-0 w-72 bg-slate-900 border-r border-white/5 z-50 transition-transform ${isSidebarOpen ? 'translate-x-0' : '-translate-x-full'}`}>
        <div className="h-full flex flex-col p-8">
          <div className="flex items-center gap-4 mb-12">
            <div className={`w-10 h-10 ${accountData.isAdmin ? 'bg-rose-500' : 'bg-indigo-600'} rounded-xl flex items-center justify-center text-white`}>
              {accountData.isAdmin ? <Crown size={24} /> : <ShieldCheck size={24} />}
            </div>
            <span className="font-black italic tracking-tighter text-xl">HORIZON</span>
          </div>
          <nav className="flex-1 space-y-2">
            {['dashboard', 'directory'].map(tab => (
              <button key={tab} onClick={() => setActiveTab(tab)} className={`w-full flex items-center gap-4 px-5 py-4 rounded-2xl font-bold uppercase text-xs tracking-widest transition-all ${activeTab === tab ? 'bg-white text-slate-900' : 'text-slate-500 hover:bg-slate-800'}`}>
                {tab === 'dashboard' ? <LayoutDashboard size={18}/> : <Users size={18}/>} {tab}
              </button>
            ))}
            {accountData.isAdmin && (
              <button onClick={() => setActiveTab('admin')} className={`w-full flex items-center gap-4 px-5 py-4 rounded-2xl font-bold uppercase text-xs tracking-widest mt-6 border-2 ${activeTab === 'admin' ? 'border-rose-500 text-rose-500 bg-rose-500/10' : 'border-dashed border-rose-500/30 text-rose-400'}`}>
                <ShieldAlert size={18} /> Owner Vault
              </button>
            )}
          </nav>
          <div className="p-6 bg-slate-800/50 rounded-[2rem] mt-auto">
            <p className="text-[9px] font-black text-slate-500 uppercase tracking-widest mb-1">Authenticated As</p>
            <p className="text-sm font-bold text-indigo-400 mb-4 truncate">@{accountData.username}</p>
            <button onClick={logout} className="w-full py-2 text-[10px] font-black bg-rose-500/10 text-rose-500 rounded-lg hover:bg-rose-500 hover:text-white transition-all uppercase tracking-widest">Logout</button>
          </div>
        </div>
      </aside>

      <main className={`flex-1 flex flex-col transition-all duration-500 ${isSidebarOpen ? 'lg:pl-72' : 'pl-0'}`}>
        <header className="h-20 border-b border-white/5 flex items-center justify-between px-10">
          <button onClick={() => setSidebarOpen(!isSidebarOpen)} className="p-2 hover:bg-slate-800 rounded-xl transition-all"><Menu size={24} /></button>
          <div className="flex items-center gap-4">
             <div className="text-right">
               <p className="text-[9px] font-black text-slate-500 uppercase">Balance</p>
               <p className="text-xl font-black text-indigo-400">${accountData.balance.toLocaleString()}</p>
             </div>
             <div className="w-10 h-10 bg-slate-800 rounded-xl flex items-center justify-center font-bold">{accountData.username[0].toUpperCase()}</div>
          </div>
        </header>

        <div className="flex-1 overflow-y-auto p-10 space-y-8">
          {activeTab === 'dashboard' && (
            <div className="grid grid-cols-1 xl:grid-cols-3 gap-8">
              <div className="xl:col-span-1 bg-slate-900 p-8 rounded-[3rem] border border-white/5 space-y-6">
                <h2 className="text-lg font-black uppercase tracking-widest flex items-center gap-3 text-indigo-400"><ArrowRightLeft size={20}/> Quick Send</h2>
                <div className="space-y-4">
                  <input className="w-full bg-slate-800 border-none rounded-2xl p-4 text-xs font-mono" placeholder="Recipient UID" value={recipientId} onChange={e => setRecipientId(e.target.value)} />
                  <div className="relative">
                    <span className="absolute left-4 top-1/2 -translate-y-1/2 text-2xl font-black text-slate-600">$</span>
                    <input type="number" className="w-full bg-slate-800 border-none rounded-2xl py-6 pl-10 pr-4 text-4xl font-black" placeholder="0" value={amount} onChange={e => setAmount(e.target.value)} />
                  </div>
                  <button onClick={handleTransfer} disabled={isProcessing || !amount} className="w-full bg-indigo-600 py-5 rounded-2xl font-black uppercase text-xs tracking-widest hover:bg-indigo-500 active:scale-95 transition-all">Authorize Payment</button>
                </div>
              </div>
              <div className="xl:col-span-2 bg-slate-900 rounded-[3rem] border border-white/5 overflow-hidden">
                <div className="p-6 border-b border-white/5 bg-slate-800/20"><p className="text-[10px] font-black text-slate-500 uppercase tracking-widest">Recent Activity</p></div>
                <table className="w-full text-left">
                   <tbody>
                     {transactions.map(tx => (
                       <tr key={tx.id} className="border-b border-white/5 last:border-0 hover:bg-white/5">
                         <td className="px-8 py-6"><p className="font-bold">{tx.merchant}</p><p className="text-[10px] text-slate-500 uppercase font-black">{tx.category}</p></td>
                         <td className={`px-8 py-6 text-right font-black ${tx.amount < 0 ? 'text-rose-500' : 'text-emerald-500'}`}>{tx.amount < 0 ? '-' : '+'}${Math.abs(tx.amount).toLocaleString()}</td>
                       </tr>
                     ))}
                   </tbody>
                </table>
              </div>
            </div>
          )}

          {activeTab === 'directory' && (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {allUsers.map(u => (
                <div key={u.uid} className="bg-slate-900 p-8 rounded-[2.5rem] border border-white/5 flex justify-between items-center group">
                  <div>
                    <p className="font-bold flex items-center gap-2">@{u.username} {u.isAdmin && <Crown size={14} className="text-rose-500"/>}</p>
                    <code className="text-[10px] text-slate-500 select-all">{u.uid}</code>
                  </div>
                  {u.uid !== appUser.uid && (
                    <button onClick={() => { setRecipientId(u.uid); setActiveTab('dashboard'); }} className="bg-indigo-600/10 text-indigo-400 p-3 rounded-xl opacity-0 group-hover:opacity-100 transition-all hover:bg-indigo-600 hover:text-white"><Send size={18}/></button>
                  )}
                </div>
              ))}
            </div>
          )}

          {activeTab === 'admin' && accountData.isAdmin && (
            <div className="space-y-8">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
                <div className="bg-rose-600 p-8 rounded-[2.5rem]"><p className="text-[10px] font-black uppercase mb-1 opacity-70">Total Assets</p><p className="text-4xl font-black">${allUsers.reduce((s,u)=>s+u.balance,0).toLocaleString()}</p></div>
                <div className="bg-slate-900 p-8 rounded-[2.5rem] border border-white/5"><p className="text-[10px] font-black uppercase mb-1 text-slate-500">Nodes</p><p className="text-4xl font-black text-emerald-500">{allUsers.length}</p></div>
              </div>
              <div className="bg-slate-900 rounded-[3rem] border border-white/5 overflow-hidden">
                <table className="w-full text-left">
                  <thead className="bg-slate-800/50 text-[10px] font-black text-slate-500 uppercase"><tr className="px-8"><th className="px-8 py-4">Node</th><th className="px-8 py-4">Balance</th><th className="px-8 py-4 text-right">Actions</th></tr></thead>
                  <tbody>
                    {allUsers.map(u => (
                      <tr key={u.uid} className="border-b border-white/5 hover:bg-white/5">
                        <td className="px-8 py-6"><p className="font-bold">@{u.username}</p><code className="text-[9px] text-slate-500">{u.uid}</code></td>
                        <td className="px-8 py-6 font-black text-indigo-400">${u.balance.toLocaleString()}</td>
                        <td className="px-8 py-6 text-right"><button onClick={() => { const b = prompt(`Balance for ${u.username}:`, u.balance); if(b!==null) updateDoc(doc(db,'artifacts',appId,'public','data','accounts',u.uid),{balance:parseFloat(b)}); }} className="bg-slate-800 px-4 py-2 rounded-xl text-[10px] font-black hover:bg-rose-500 transition-all">OVERRIDE</button></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      </main>
    </div>
  );
};

const Menu = ({ size }) => <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="3" y1="12" x2="21" y2="12"></line><line x1="3" y1="6" x2="21" y2="6"></line><line x1="3" y1="18" x2="21" y2="18"></line></svg>;

export default App;

```
