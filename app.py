import streamlit as st
import requests
import json
import os

# --- 1. Configuration & API Setup ---
SCRIPT_DIR = os.path.dirname(__file__)
CONFIG_PATH = os.path.join(SCRIPT_DIR, 'config.json')
TEMPLATES_DIR = os.path.join(SCRIPT_DIR, 'templates')

# Ensure the templates directory exists
os.makedirs(TEMPLATES_DIR, exist_ok=True)

@st.cache_data(ttl=3000)
def get_config_and_token():
    """Loads configuration and fetches the OAuth2 access token."""
    try:
        if not os.path.exists(CONFIG_PATH):
            st.error("Configuration file 'config.json' not found. Please create one based on the example.")
            return None, None
            
        with open(CONFIG_PATH, 'r') as f:
            config = json.load(f)
            
        base_url = config.get("base_url", "").rstrip('/')
        if not base_url:
            st.error("Missing 'base_url' in config.json (e.g., https://eu.ninjarmm.com)")
            return None, None

        auth_payload = {
            "grant_type": "client_credentials",
            "client_id": config.get("client_id"),
            "client_secret": config.get("client_secret"),
            "scope": config.get("scope", "management control monitoring")
        }
        
        res = requests.post(f"{base_url}/oauth/token", data=auth_payload)
        res.raise_for_status()
        
        return base_url, res.json()["access_token"]
        
    except Exception as e:
        st.error(f"Authentication error: {e}")
        return None, None

def get_api_session():
    """Returns the base URL and authorized headers."""
    base_url, token = get_config_and_token()
    if token:
        headers = {
            "Authorization": f"Bearer {token}", 
            "Accept": "application/json", 
            "Content-Type": "application/json"
        }
        return base_url, headers
    return None, None

# --- 2. Data Fetching ---
@st.cache_data(ttl=300)
def get_organizations():
    base_url, headers = get_api_session()
    if not headers: return []
    res = requests.get(f"{base_url}/v2/organizations", headers=headers)
    return res.json() if res.status_code == 200 else []

@st.cache_data(ttl=3600)
def get_roles():
    base_url, headers = get_api_session()
    if not headers: return []
    res = requests.get(f"{base_url}/v2/noderole/list", headers=headers)
    return sorted(res.json(), key=lambda x: x.get('name', '')) if res.status_code == 200 else []

@st.cache_data(ttl=3600)
def get_policies():
    base_url, headers = get_api_session()
    if not headers: return []
    res = requests.get(f"{base_url}/v2/policies", headers=headers)
    policies = sorted(res.json(), key=lambda x: x.get('name', '')) if res.status_code == 200 else []
    
    # Insert special options at the top
    policies.insert(0, {"id": "IGNORE", "name": "-- IGNORE (Keep current) --"})
    policies.insert(1, {"id": "INHERIT", "name": "❌ INHERIT (Remove specific assignment)"})
    return policies

# --- Helper Functions for Templates ---
def get_saved_templates():
    return [f for f in os.listdir(TEMPLATES_DIR) if f.endswith('.json')]

def apply_template_to_session(template_data, valid_policy_ids):
    """Applies a loaded template to the Streamlit session state."""
    for mapping in template_data:
        role_id = mapping.get("nodeRoleId")
        policy_id = mapping.get("policyId")
        key = f"role_{role_id}"
        
        if policy_id in valid_policy_ids:
            st.session_state[key] = policy_id
        else:
            st.warning(f"Warning: Policy ID {policy_id} not found in NinjaOne. Role {role_id} mapping ignored.")

# --- INITIALIZE SESSION STATE ---
if 'step2_unlocked' not in st.session_state:
    st.session_state.step2_unlocked = False
if 'saved_mappings' not in st.session_state:
    st.session_state.saved_mappings = {}

# --- 3. GUI Layout & Logic ---
st.set_page_config(page_title="NinjaOne Policy Manager", layout="wide")
st.title("🥷 NinjaOne Policy Manager")

# Load initial data
orgs = get_organizations()
roles = get_roles()
policies = get_policies()

if not orgs or not roles:
    st.stop() # Stops execution if API fails (error is handled in fetchers)

valid_policy_ids = [p['id'] for p in policies]

# --- TEMPLATE MANAGEMENT (Top Section) ---
with st.expander("📁 Manage Templates (Load & Import)"):
    tab1, tab2 = st.tabs(["Load from App", "Import File (Upload)"])
    
    with tab1:
        saved_tpls = get_saved_templates()
        if saved_tpls:
            selected_tpl = st.selectbox("Select saved template:", ["-- Please select --"] + saved_tpls)
            if st.button("Apply Template") and selected_tpl != "-- Please select --":
                with open(os.path.join(TEMPLATES_DIR, selected_tpl), 'r') as f:
                    tpl_data = json.load(f)
                apply_template_to_session(tpl_data, valid_policy_ids)
                st.success(f"Template '{selected_tpl}' applied! (Check Step 1)")
                st.rerun()
        else:
            st.info("No templates saved in the app yet.")
            
    with tab2:
        uploaded_file = st.file_uploader("Upload an existing template (.json)", type=['json'])
        if uploaded_file is not None:
            if st.button("Apply Uploaded Template"):
                tpl_data = json.load(uploaded_file)
                apply_template_to_session(tpl_data, valid_policy_ids)
                st.success("Template successfully imported! (Check Step 1)")
                st.rerun()

st.markdown("---")

# --- STEP 1: Configure Mappings ---
st.header("1. Assign Policies to Device Roles")

current_mappings = {}
col1, col2 = st.columns(2)
policy_options = {p['id']: p['name'] for p in policies}

with st.form("policy_form"):
    st.write("Select the desired policy for each device role:")
    
    for i, role in enumerate(roles):
        target_col = col1 if i % 2 == 0 else col2
        with target_col:
            # Session-State keys (role_123) automatically bind if set by a template
            selected_policy = st.selectbox(
                f"🖥️ {role['name']}", 
                options=list(policy_options.keys()), 
                format_func=lambda x: policy_options[x],
                key=f"role_{role['id']}"
            )
            if selected_policy is not None:
                current_mappings[role['id']] = selected_policy

    st.markdown("---")
    submitted = st.form_submit_button("Prepare Changes & Show Options")

if submitted:
    st.session_state.step2_unlocked = True
    st.session_state.saved_mappings = current_mappings

# --- STEP 2 & 3: Review, Save & Push ---
if st.session_state.step2_unlocked:
    st.markdown("---")
    st.header("2. Review & Save Template")
    
    active_mappings = st.session_state.saved_mappings
    
    # Generate human-readable preview
    preview = {
        next(r['name'] for r in roles if r['id'] == role_id): policy_options[pol_id] 
        for role_id, pol_id in active_mappings.items() if pol_id != "IGNORE"
    }
    
    if not preview:
        st.info("No changes planned (all roles are set to 'IGNORE').")
    else:
        st.write("The following assignments have been prepared:")
        st.json(preview)

        # Build payload for saving (exclude IGNORE and INHERIT flags)
        save_payload = [{"nodeRoleId": r, "policyId": p} for r, p in active_mappings.items() if p not in ["IGNORE", "INHERIT"]]
        
        tpl_col1, tpl_col2 = st.columns(2)
        with tpl_col1:
            st.write("**Save internally:**")
            tpl_name = st.text_input("Template name (without .json):", placeholder="e.g., Base_Windows_Setup")
            if st.button("💾 Save to App"):
                if tpl_name:
                    safe_name = "".join([c for c in tpl_name if c.isalnum() or c in ('_', '-')]).rstrip()
                    if safe_name:
                        file_path = os.path.join(TEMPLATES_DIR, f"{safe_name}.json")
                        with open(file_path, "w") as f:
                            json.dump(save_payload, f, indent=4)
                        st.success(f"Saved successfully as '{safe_name}.json'!")
                    else:
                        st.error("Invalid template name.")
                else:
                    st.warning("Please enter a name.")
                    
        with tpl_col2:
            st.write("**Download to PC:**")
            template_json_str = json.dumps(save_payload, indent=4)
            st.download_button(
                label="⬇️ Download file",
                data=template_json_str,
                file_name="ninja_policy_template.json",
                mime="application/json"
            )

        st.markdown("---")
        st.header("3. Rollout to Organizations")
        
        org_options = {org['id']: org['name'] for org in orgs}
        selected_org_ids = st.multiselect(
            "Select one or more organizations to apply these policies to:", 
            options=list(org_options.keys()), 
            format_func=lambda x: org_options[x],
            help="Type to search. You can select multiple organizations."
        )

        if st.button(f"🚀 Push to {len(selected_org_ids)} selected organizations", type="primary"):
            if not selected_org_ids:
                st.warning("⚠️ Please select at least one organization first!")
            else:
                base_url, headers = get_api_session()
                progress_text = "Starting rollout..."
                my_bar = st.progress(0, text=progress_text)
                
                success_count = 0
                error_messages = []

                for i, org_id in enumerate(selected_org_ids):
                    org_name = org_options[org_id]
                    my_bar.progress((i) / len(selected_org_ids), text=f"Pushing to: {org_name}...")
                    
                    get_url = f"{base_url}/v2/organization/{org_id}"
                    push_url = f"{base_url}/v2/organization/{org_id}/policies"
                    
                    # 1. Fetch current status
                    org_res = requests.get(get_url, headers=headers)
                    if org_res.status_code == 200:
                        org_data = org_res.json()
                        existing_policies = org_data.get('policies', [])
                        merged_policies = {p['nodeRoleId']: p['policyId'] for p in existing_policies}
                        
                        # 2. Merge changes intelligently
                        for role_id, policy_id in active_mappings.items():
                            if policy_id == "IGNORE":
                                continue
                            elif policy_id == "INHERIT":
                                if role_id in merged_policies:
                                    del merged_policies[role_id]
                            else:
                                merged_policies[role_id] = policy_id
                        
                        # 3. Format for API
                        payload_policies = [{"nodeRoleId": r, "policyId": p} for r, p in merged_policies.items()]
                        
                        # 4. Push updates
                        put_res = requests.put(push_url, headers=headers, json=payload_policies)
                        
                        if put_res.status_code in [200, 201, 204]:
                            success_count += 1
                        else:
                            error_messages.append(f"{org_name}: API Error {put_res.status_code} - {put_res.text}")
                    else:
                        error_messages.append(f"{org_name}: Could not load current data")

                my_bar.progress(1.0, text="Rollout complete!")
                
                if success_count == len(selected_org_ids):
                    st.success(f"Successfully pushed to all {success_count} organizations!")
                    st.balloons()
                else:
                    st.warning(f"⚠️ Rollout finished. {success_count} successful. Encountered {len(error_messages)} errors.")
                    for err in error_messages:
                        st.error(err)
