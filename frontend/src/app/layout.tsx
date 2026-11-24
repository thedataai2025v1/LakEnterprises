import type { Metadata } from 'next';
import './globals.css';
import { AuthProvider } from '@/context/auth-context';
import { Sidebar } from '@/components/navigation/sidebar';
import { Navbar } from '@/components/navigation/navbar';

export const metadata: Metadata = {
  title: 'LakEnterprises — Console UI',
  description: 'Enterprise Agentic Governance & Workflow Console',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-slate-50 flex text-slate-900 antialiased">
        <AuthProvider>
          <Sidebar />
          <div className="flex-1 flex flex-col min-w-0 min-h-screen">
            <Navbar />
            <main className="flex-1 p-6 md:p-8 overflow-y-auto">
              {children}
            </main>
          </div>
        </AuthProvider>
      </body>
    </html>
  );
}
