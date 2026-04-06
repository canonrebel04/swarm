## 2026-03-31 - Hardcoded Default API Key in Server

**Vulnerability:** The Swarm API server had a hardcoded default API key `swarm_dev_key` that was used if the `SWARM_API_KEY` environment variable was not set. This also existed in the frontend `app.js`.

**Learning:** Providing "dev-friendly" defaults for security-sensitive configurations like API keys often leads to them being left in production environments, creating a massive security hole.

**Prevention:** Always "fail closed" for security configurations. If a required secret is missing, the application should refuse to start or return an error for all protected requests, rather than falling back to a known default. Use clear error messages to guide the user to configure the necessary environment variables.
