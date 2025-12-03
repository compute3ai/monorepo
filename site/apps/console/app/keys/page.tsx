"use client";

import React, { useEffect, useState } from "react";
import { Header, Footer, useAuth, Modal, AlertDialog, formatDateTime } from "@compute3/shared-ui";
import { useRouter } from "next/navigation";

interface ApiKey {
  key_id: string;
  name: string;
  api_key_preview: string;
  last4: string;
  is_active: boolean;
  created_at: string;
  last_used_at: string | null;
}

interface NewApiKey {
  key_id: string;
  name: string;
  api_key: string; // Full key - only shown once on creation
  is_active: boolean;
  created_at: string;
  last_used_at: string | null;
}

export default function ApiKeysPage() {
  const { isLoading, isAuthenticated } = useAuth();
  const router = useRouter();
  const [apiKeys, setApiKeys] = useState<ApiKey[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [newKeyName, setNewKeyName] = useState("");
  const [createdKey, setCreatedKey] = useState<NewApiKey | null>(null);
  const [creating, setCreating] = useState(false);
  const [copiedKey, setCopiedKey] = useState(false);
  const [alertDialog, setAlertDialog] = useState<{
    isOpen: boolean;
    title: string;
    message: string;
    type: "info" | "warning" | "error" | "success";
    onConfirm?: () => void | Promise<void>;
    showCancel?: boolean;
  }>({
    isOpen: false,
    title: "",
    message: "",
    type: "info",
  });

  useEffect(() => {
    if (!isLoading && !isAuthenticated) {
      router.push('/');
    }
  }, [isLoading, isAuthenticated, router]);

  useEffect(() => {
    if (isAuthenticated) {
      fetchApiKeys();
    }
  }, [isAuthenticated]);

  const fetchApiKeys = async () => {
    setLoading(true);
    setError(null);
    try {
      const authToken = document.cookie
        .split('; ')
        .find(row => row.startsWith('auth_token='))
        ?.split('=')[1];

      if (!authToken) {
        setError('No auth token found');
        setLoading(false);
        return;
      }

      const response = await fetch(`${process.env.NEXT_PUBLIC_AUTH_BACKEND}/keys`, {
        method: 'GET',
        headers: {
          'Authorization': `Bearer ${authToken}`,
          'Content-Type': 'application/json'
        }
      });

      if (response.ok) {
        const keys = await response.json();
        setApiKeys(keys);
      } else if (response.status === 404) {
        // 404 means no keys exist yet, not an error
        setApiKeys([]);
      } else {
        const errorData = await response.json();
        setError(errorData.detail || 'Failed to load API keys');
      }
    } catch (error) {
      console.error('Error fetching API keys:', error);
      setError(error instanceof Error ? error.message : 'Unknown error');
    } finally {
      setLoading(false);
    }
  };

  const handleCreateKey = async () => {
    if (!newKeyName.trim()) {
      setAlertDialog({
        isOpen: true,
        title: "Validation Error",
        message: 'Please enter a name for the API key',
        type: "warning",
      });
      return;
    }

    setCreating(true);
    try {
      const authToken = document.cookie
        .split('; ')
        .find(row => row.startsWith('auth_token='))
        ?.split('=')[1];

      if (!authToken) return;

      const response = await fetch(`${process.env.NEXT_PUBLIC_AUTH_BACKEND}/keys`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${authToken}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ name: newKeyName })
      });

      if (response.ok) {
        const newKey = await response.json();
        setCreatedKey(newKey);
        setNewKeyName("");
        setShowCreateModal(false);
        fetchApiKeys();
      } else {
        const error = await response.json();
        setAlertDialog({
          isOpen: true,
          title: "Error",
          message: error.detail || 'Failed to create API key',
          type: "error",
        });
      }
    } catch (error) {
      console.error('Error creating API key:', error);
      setAlertDialog({
        isOpen: true,
        title: "Error",
        message: 'Failed to create API key',
        type: "error",
      });
    } finally {
      setCreating(false);
    }
  };

  const handleDeactivateKey = async (keyId: string) => {
    setAlertDialog({
      isOpen: true,
      title: "Deactivate API Key",
      message: 'Are you sure you want to deactivate this API key? This action cannot be undone and the key will no longer work.',
      type: "warning",
      showCancel: true,
      onConfirm: async () => {
        try {
          const authToken = document.cookie
            .split('; ')
            .find(row => row.startsWith('auth_token='))
            ?.split('=')[1];

          if (!authToken) return;

          const response = await fetch(`${process.env.NEXT_PUBLIC_AUTH_BACKEND}/keys/${keyId}`, {
            method: 'DELETE',
            headers: {
              'Authorization': `Bearer ${authToken}`,
              'Content-Type': 'application/json'
            }
          });

          if (response.ok) {
            fetchApiKeys();
          } else {
            const error = await response.json();
            setAlertDialog({
              isOpen: true,
              title: "Error",
              message: error.detail || 'Failed to deactivate API key',
              type: "error",
            });
          }
        } catch (error) {
          console.error('Error deactivating API key:', error);
          setAlertDialog({
            isOpen: true,
            title: "Error",
            message: 'Failed to deactivate API key',
            type: "error",
          });
        }
      }
    });
  };

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    setCopiedKey(true);
    setTimeout(() => setCopiedKey(false), 2000);
  };

  if (isLoading || !isAuthenticated) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-gray-900 text-xl">Loading...</div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex flex-col overflow-x-hidden">
      <Header />

      <main className="flex-1 pt-20 relative">
        <div className="max-w-[1400px] mx-auto px-4 sm:px-6 lg:px-8 py-12">
          <div className="flex justify-between items-center mb-8">
            <h1 className="text-4xl font-bold text-gray-900">API Keys</h1>
            <button
              onClick={() => setShowCreateModal(true)}
              className="btn-primary text-white font-semibold py-2 px-6 rounded-lg"
            >
              Create New Key
            </button>
          </div>

          {loading && <div className="text-gray-600">Loading API keys...</div>}
          {error && <div className="text-red-600 mb-4">Error: {error}</div>}

          {!loading && !error && apiKeys.length === 0 && (
            <div className="bg-white p-8 rounded-lg shadow text-center">
              <p className="text-gray-600 mb-4">You don't have any API keys yet.</p>
              <button
                onClick={() => setShowCreateModal(true)}
                className="btn-primary text-white font-semibold py-2 px-6 rounded-lg"
              >
                Create Your First API Key
              </button>
            </div>
          )}

          {!loading && apiKeys.length > 0 && (
            <div className="bg-white rounded-lg shadow overflow-hidden">
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-6 py-3 text-left text-xs font-semibold text-gray-600 uppercase tracking-wider">
                      Name
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-semibold text-gray-600 uppercase tracking-wider">
                      Key
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-semibold text-gray-600 uppercase tracking-wider">
                      Status
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-semibold text-gray-600 uppercase tracking-wider">
                      Created
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-semibold text-gray-600 uppercase tracking-wider">
                      Last Used
                    </th>
                    <th className="px-6 py-3 text-right text-xs font-semibold text-gray-600 uppercase tracking-wider">
                      Actions
                    </th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {apiKeys.map((key) => (
                    <tr key={key.key_id} className="hover:bg-gray-50">
                      <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">
                        {key.name}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm font-mono text-gray-600">
                        {key.api_key_preview}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <span className={`px-2 py-1 inline-flex text-xs leading-5 font-semibold rounded ${key.is_active ? 'bg-green-100 text-green-800' : 'bg-gray-100 text-gray-800'}`}>
                          {key.is_active ? 'Active' : 'Inactive'}
                        </span>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                        {formatDateTime(key.created_at)}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                        {formatDateTime(key.last_used_at)}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                        {key.is_active ? (
                          <button
                            onClick={() => handleDeactivateKey(key.key_id)}
                            className="text-red-600 hover:text-red-900"
                          >
                            Deactivate
                          </button>
                        ) : (
                          <span className="text-gray-400 italic">Deactivated</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </main>

      <Footer />

      {/* Create Key Modal */}
      {showCreateModal && (
        <Modal
          isOpen={showCreateModal}
          onClose={() => {
            setShowCreateModal(false);
            setNewKeyName("");
          }}
          title="Create New API Key"
          maxWidth="md"
        >
          <div className="space-y-6">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Key Name
              </label>
              <input
                type="text"
                value={newKeyName}
                onChange={(e) => setNewKeyName(e.target.value)}
                placeholder="e.g., Production Server"
                className="w-full border border-gray-300 rounded-lg px-4 py-2"
                disabled={creating}
              />
            </div>
            <div className="flex gap-3">
              <button
                onClick={handleCreateKey}
                disabled={creating}
                className="flex-1 btn-primary text-white font-semibold py-2 px-4 rounded-lg disabled:opacity-50"
              >
                {creating ? 'Creating...' : 'Create Key'}
              </button>
              <button
                onClick={() => {
                  setShowCreateModal(false);
                  setNewKeyName("");
                }}
                disabled={creating}
                className="flex-1 btn-secondary font-semibold py-2 px-4 rounded-lg"
              >
                Cancel
              </button>
            </div>
          </div>
        </Modal>
      )}

      {/* Show Created Key Modal */}
      {createdKey && (
        <Modal
          isOpen={!!createdKey}
          onClose={() => setCreatedKey(null)}
          title="API Key Created!"
          maxWidth="2xl"
        >
          <div className="space-y-6">
            <div className="bg-yellow-50 border-l-4 border-yellow-400 p-4">
              <p className="text-sm text-yellow-700">
                <strong>Important:</strong> Make sure to copy your API key now. You won't be able to see it again!
              </p>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Your API Key
              </label>
              <div className="flex gap-2">
                <input
                  type="text"
                  value={createdKey.api_key}
                  readOnly
                  className="flex-1 font-mono text-sm border border-gray-300 rounded-lg px-4 py-2 bg-gray-50"
                />
                <button
                  onClick={() => copyToClipboard(createdKey.api_key)}
                  className="btn-primary text-white font-semibold py-2 px-4 rounded-lg"
                >
                  {copiedKey ? 'Copied!' : 'Copy'}
                </button>
              </div>
            </div>
            <button
              onClick={() => setCreatedKey(null)}
              className="w-full btn-secondary font-semibold py-2 px-4 rounded-lg"
            >
              Done
            </button>
          </div>
        </Modal>
      )}

      <AlertDialog
        isOpen={alertDialog.isOpen}
        onClose={() => setAlertDialog({ ...alertDialog, isOpen: false })}
        title={alertDialog.title}
        message={alertDialog.message}
        type={alertDialog.type}
        onConfirm={alertDialog.onConfirm}
        showCancel={alertDialog.showCancel}
      />
    </div>
  );
}
