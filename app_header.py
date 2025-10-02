import streamlit as st
import base64

def render_custom_header():
    # Load logo image and encode to base64
    with open("app/assets/flora_carbon_logo.png", "rb") as image_file:
        encoded_logo = base64.b64encode(image_file.read()).decode()

    # Custom CSS styling for header
    st.markdown(f"""
        <style>
        .custom-header {{
            display: flex;
            align-items: center;
            background-color: #0d0d0d;
            padding: 1.5rem;
            border-bottom: 2px solid #00f5c8;
            box-shadow: 0 4px 20px rgba(0, 245, 200, 0.25);
            margin-bottom: 1.5rem;
        }}
        .logo-container img {{
            height: 60px;
            border-radius: 10px;
            margin-right: 1.2rem;
            box-shadow: 0 0 15px rgba(0,255,200,0.3);
        }}
        .title-container h1 {{
            margin: 0;
            font-size: 2rem;
            color: #00f5c8;
            text-shadow: 0 0 6px #00f5c8, 0 0 10px #00f5c8;
            font-family: 'Segoe UI', sans-serif;
        }}
        .title-container p {{
            margin: 0;
            font-size: 1rem;
            color: #bbbbbb;
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
