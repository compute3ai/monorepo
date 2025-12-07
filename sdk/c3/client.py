"""Main C3 client"""
from .config import get_api_key, get_api_url
from .http import HTTPClient
from .billing import Billing
from .jobs import Jobs
from .user import UserAPI
from .instances import Instances
from .renders import Renders


class C3:
    """
    C3 API Client

    Usage:
        from c3 import C3

        c3 = C3()  # Uses C3_API_KEY from env or ~/.c3/config
        # or
        c3 = C3(api_key="your_key")

        # Billing
        balance = c3.billing.balance()
        print(f"Balance: ${balance.total}")

        # Jobs
        job = c3.jobs.create(
            image="nvidia/cuda:12.0",
            gpu_type="l40s",
            command="python train.py"
        )
        print(f"Job: {job.job_id}")

        # User
        user = c3.user.get()
    """

    def __init__(self, api_key: str = None, api_url: str = None):
        self._api_key = api_key or get_api_key()
        if not self._api_key:
            raise ValueError(
                "API key required. Set C3_API_KEY env var, "
                "create ~/.c3/config, or pass api_key parameter."
            )

        self._api_url = api_url or get_api_url()
        self._http = HTTPClient(self._api_url, self._api_key)

        # API namespaces
        self.billing = Billing(self._http)
        self.jobs = Jobs(self._http)
        self.user = UserAPI(self._http)
        self.instances = Instances(self._http)
        self.renders = Renders(self._http)

    @property
    def api_url(self) -> str:
        return self._api_url
