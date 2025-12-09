// Type definitions for browser wallet extensions

interface EthereumProvider {
  request: (args: { method: string; params?: any[] }) => Promise<any>;
  on: (event: string, handler: (...args: any[]) => void) => void;
  removeListener: (event: string, handler: (...args: any[]) => void) => void;
  isMetaMask?: boolean;
  isPhantom?: boolean;
  selectedAddress?: string | null;
  chainId?: string;
}

interface PhantomEthereum extends EthereumProvider {
  isPhantom: true;
}

declare global {
  interface Window {
    ethereum?: EthereumProvider;
    phantom?: {
      ethereum?: PhantomEthereum;
    };
  }
}

export {};
