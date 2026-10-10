import { createContext, useCallback, useContext, useRef, useState } from 'react';

const ToastContext = createContext(() => {});

export function ToastProvider({ children }) {
  const [msg, setMsg] = useState(null);
  const timer = useRef(0);
  const show = useCallback((text) => {
    setMsg({ text, id: Date.now() });
    clearTimeout(timer.current);
    timer.current = setTimeout(() => setMsg(null), 2200);
  }, []);
  return (
    <ToastContext.Provider value={show}>
      {children}
      {msg && (
        <div className="toast" key={msg.id} role="status">
          {msg.text}
        </div>
      )}
    </ToastContext.Provider>
  );
}

export const useToast = () => useContext(ToastContext);
