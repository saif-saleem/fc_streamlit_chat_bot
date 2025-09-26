import streamlit as st
import base64

def render_custom_header():
    # Load logo image and encode to base64
    with open("app/assets/flora_carbon_logo.png", "rb") as image_file:
        encoded_logo = base64.b64encode(image_file.read()).decode()

    # Custom CSS styling
    st.markdown(f"""
        <style>
        .custom-header {{
            display: flex;
            align-items: center;
            background-color: #002E29;
            padding: 1.5rem;
            border-radius: 12px;
            box-shadow: 0 0 25px rgba(0, 255, 200, 0.25);
            margin-bottom: 1rem;
        }}
        .logo-container img {{
            height: 64px;
            border-radius: 12px;
            margin-right: 1.2rem;
            box-shadow: 0 0 15px rgba(0,255,255,0.2);
        }}
        .title-container h1 {{
            margin: 0;
            font-size: 2.5rem;
            color: #39ff14;
            text-shadow: 0 0 5px #39ff14, 0 0 10px #39ff14;
            font-family: 'Segoe UI', sans-serif;
        }}
        .title-container p {{
            margin: 0;
            font-size: 1.1rem;
            color: #e0f2f1;
            font-family: 'Segoe UI', sans-serif;
        }}
        </style>

        <div class="custom-header">
            <div class="logo-container">
                <img src="data:image/png;base64,{encoded_logo}" alt="Flora Carbon Logo" />
            </div>
            <div class="title-container">
                <h1>Flora Carbon GPT</h1>
                <p>Your expert assistant for carbon credit standards & certifications</p>
            </div>
        </div>
    """, unsafe_allow_html=True)
