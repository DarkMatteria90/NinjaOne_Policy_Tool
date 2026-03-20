# NinjaOne_Policy_Tool
Streamlit-based web interface to manage and bulk-assign device policies across multiple organizations in NinjaOne via API v2.

# NinjaOne Policy Manager (GUI)

A Streamlit-based web interface to manage and bulk-assign device policies across multiple organizations in NinjaOne via API v2.

## Features
* **Live Search:** Quickly find device roles, policies, and organizations.
* **Template Engine:** Save your standard policy assignments (e.g., "Base Windows Build") internally or export them as JSON.
* **Safe Updates:** Only updates the device roles you explicitly change. Leaves existing configurations intact using intelligent merging.
* **Bulk Rollout:** Select multiple organizations at once and apply your policy templates with a single click.

## Setup Instructions
1. Clone the repository.
2. Install the requirements: `pip install -r requirements.txt`
3. Copy the `config.example.json` file and rename it to `config.json`.
4. Enter your NinjaOne API credentials in the `config.json` (Ensure you generate a Machine-to-Machine App with `management`, `monitoring`, and `control` scopes).
5. Start the app: `streamlit run app.py`
