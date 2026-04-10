import React, { useEffect, useRef, useState } from 'react';
import { Bell, ChevronsLeft, ChevronsRight, UserCircle2, LogOut } from 'lucide-react';
import { useAuth } from '../context/AuthContext';

const Navbar = ({ sidebarCollapsed, onToggleSidebar }) => {
  const { user, logout } = useAuth();
  const [open, setOpen] = useState(false);
  const profileRef = useRef(null);

  useEffect(() => {
    const onOutsideClick = (event) => {
      if (!profileRef.current?.contains(event.target)) {
        setOpen(false);
      }
    };

    document.addEventListener('mousedown', onOutsideClick);
    return () => {
      document.removeEventListener('mousedown', onOutsideClick);
    };
  }, []);

  const handleLogout = async () => {
    await logout();
    setOpen(false);
  };

  return (
    <header className="bg-panel border-b border-border h-16 flex items-center justify-between px-6">
      <button
        className="hidden lg:flex items-center gap-2 text-gray-400 hover:text-white transition-colors"
        onClick={onToggleSidebar}
        type="button"
      >
        {sidebarCollapsed ? <ChevronsRight size={20} /> : <ChevronsLeft size={20} />}
        <span className="text-sm">{sidebarCollapsed ? 'Expand Menu' : 'Collapse Menu'}</span>
      </button>

      <div className="flex items-center gap-4 ml-auto">
        <button className="text-gray-400 hover:text-white transition-colors" type="button">
          <Bell size={20} />
        </button>

        <div className="relative" ref={profileRef}>
          <button
            className="flex items-center gap-2 text-gray-300 hover:text-white transition-colors"
            onClick={() => setOpen((value) => !value)}
            type="button"
          >
            {user?.picture_url ? (
              <img src={user.picture_url} alt="Profile" className="h-8 w-8 rounded-full object-cover border border-border" />
            ) : (
              <UserCircle2 size={28} />
            )}
          </button>

          {open && (
            <div className="absolute right-0 mt-3 w-72 rounded-xl border border-border bg-[#0f151f] shadow-xl p-3 z-30">
              <div className="flex items-center gap-3 pb-3 border-b border-border">
                {user?.picture_url ? (
                  <img src={user.picture_url} alt="Profile" className="h-10 w-10 rounded-full object-cover border border-border" />
                ) : (
                  <UserCircle2 size={34} className="text-gray-400" />
                )}
                <div className="min-w-0">
                  <p className="text-sm font-semibold text-white truncate">{user?.name || 'Authenticated User'}</p>
                  <p className="text-xs text-gray-400 truncate">{user?.email || ''}</p>
                </div>
              </div>

              <button
                type="button"
                onClick={handleLogout}
                className="mt-3 w-full rounded-md border border-red-500/30 bg-red-500/10 text-red-300 hover:bg-red-500/20 transition-colors px-3 py-2 text-sm flex items-center justify-center gap-2"
              >
                <LogOut size={16} />
                Logout
              </button>
            </div>
          )}
        </div>
      </div>
    </header>
  );
};

export default Navbar;
