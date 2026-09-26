import { Suspense, useState } from 'react';
import { QueryClientProvider } from '@tanstack/react-query';
import { RouterProvider } from 'react-router-dom';
import { LoadingState } from '@/shared/ui/feedback';
import { createQueryClient } from './queryClient';
import { router } from './router';

export function App() {
  const [client] = useState(createQueryClient);
  return (
    <QueryClientProvider client={client}>
      <Suspense fallback={<div className="min-h-screen"><LoadingState /></div>}>
        <RouterProvider router={router} future={{ v7_startTransition: true }} />
      </Suspense>
    </QueryClientProvider>
  );
}
