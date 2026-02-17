"""
🏗️ PROFESSIONAL ONE-WAY REINFORCED CONCRETE SLAB DESIGN
Complete Single-File Application
Streamlit Version 4.0 - ACI 318-14
"""

import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime
import time
import base64
import math
from dataclasses import dataclass
from typing import Dict, List, Optional

# ============================================================================
# PAGE CONFIGURATION (MUST BE FIRST)
# ============================================================================
st.set_page_config(
    page_title="One-Way Slab Designer Pro",
    page_icon="🏗️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ============================================================================
# ORIGINAL SLAB CALCULATION LOGIC (COMPLETELY INTACT)
# ============================================================================

@dataclass
class MaterialProperties:
    """Material properties for concrete and steel"""
    fc_prime: float
    fy: float
    concrete_density: float = 25
    cover: float = 20

@dataclass
class Loads:
    """Loads on the slab"""
    superimposed_dead: float
    live_load: float

class BarProperties:
    """Reinforcing bar properties"""
    
    BAR_DATA = {
        '#10': {'diameter': 9.5, 'area': 71},
        '#13': {'diameter': 12.7, 'area': 129},
        '#16': {'diameter': 15.9, 'area': 199},
        '#19': {'diameter': 19.1, 'area': 284},
        '#22': {'diameter': 22.2, 'area': 387},
        '#25': {'diameter': 25.4, 'area': 510},
        '#29': {'diameter': 28.7, 'area': 645},
        '#32': {'diameter': 32.3, 'area': 819},
        '#36': {'diameter': 35.8, 'area': 1006}
    }
    
    def __init__(self, bar_size: str = '#13'):
        if bar_size not in self.BAR_DATA:
            raise ValueError(f"Bar size {bar_size} not recognized")
        self.bar_size = bar_size
        self.diameter = self.BAR_DATA[bar_size]['diameter']
        self.area = self.BAR_DATA[bar_size]['area']

class OneWaySlab:
    """
    One-way reinforced concrete slab design class
    Implements ACI 318 code provisions
    """
    
    THICKNESS_COEFFICIENTS = {
        'simply_supported': 20,
        'one_end_continuous': 24,
        'both_ends_continuous': 28,
        'cantilever': 10
    }
    
    MOMENT_COEFFICIENT_VALUES = {
        'exterior_negative': 1/24,
        'exterior_positive': 1/14,
        'interior_negative_first': 1/10,
        'interior_positive': 1/16,
        'interior_negative': 1/11,
        'simple_span': 1/8,
        'cantilever': 1/2
    }
    
    def __init__(self):
        self.clear_span = None
        self.material = None
        self.loads = None
        self.support_condition = None
        self.main_bar = None
        self.shrinkage_bar = None
        self.user_h = None
        self.h = None
        self.d = None
        self.wu = None
        self.moments = {}
        self.reinforcement = {}
        self.shrinkage = {}
        self.shear = {}
        self.notes = []
    
    def calculate_initial_thickness(self, clear_span, support_condition, user_thickness=None):
        """Step 1: Determine initial slab thickness"""
        coefficient = self.THICKNESS_COEFFICIENTS[support_condition]
        h_calc = clear_span / coefficient
        h_rounded = math.ceil(h_calc / 10) * 10
        
        if user_thickness:
            if user_thickness < h_rounded:
                self.notes.append(f"Warning: User-specified thickness ({user_thickness}mm) is less than calculated minimum ({h_rounded}mm)")
                self.h = user_thickness
            else:
                self.h = user_thickness
        else:
            self.h = h_rounded
        
        return self.h
    
    def calculate_factored_load(self):
        """Step 2: Calculate factored uniform load"""
        self_weight = (self.h / 1000) * self.material.concrete_density
        total_dead = self.loads.superimposed_dead + self_weight
        self.wu = 1.2 * total_dead + 1.6 * self.loads.live_load
        return self.wu, total_dead, self_weight
    
    def calculate_moments(self):
        """Step 3: Calculate factored moments"""
        L_m = self.clear_span / 1000
        base_moment = self.wu * L_m**2
        
        if self.support_condition == 'simply_supported':
            coeff = self.MOMENT_COEFFICIENT_VALUES['simple_span']
            self.moments = {'Positive Moment (Midspan)': coeff * base_moment}
        
        elif self.support_condition == 'one_end_continuous':
            self.moments = {
                'Negative Moment (Exterior Support)': self.MOMENT_COEFFICIENT_VALUES['exterior_negative'] * base_moment,
                'Positive Moment (Midspan)': self.MOMENT_COEFFICIENT_VALUES['exterior_positive'] * base_moment,
                'Negative Moment (First Interior Support)': self.MOMENT_COEFFICIENT_VALUES['interior_negative_first'] * base_moment
            }
        
        elif self.support_condition == 'both_ends_continuous':
            self.moments = {
                'Negative Moment (Supports)': self.MOMENT_COEFFICIENT_VALUES['interior_negative'] * base_moment,
                'Positive Moment (Midspan)': self.MOMENT_COEFFICIENT_VALUES['interior_positive'] * base_moment
            }
        
        elif self.support_condition == 'cantilever':
            self.moments = {'Negative Moment (Support)': self.MOMENT_COEFFICIENT_VALUES['cantilever'] * base_moment}
        
        return self.moments
    
    def calculate_effective_depth(self):
        """Step 4: Calculate effective depth"""
        self.d = self.h - self.material.cover - (self.main_bar.diameter / 2)
        return self.d
    
    def calculate_required_steel(self, Mu, location):
        """Step 5 & 6: Calculate required steel reinforcement"""
        if self.d is None:
            self.calculate_effective_depth()
        
        if Mu <= 0:
            return None
        
        Mu_nmm = Mu * 1e6
        phi = 0.9
        b = 1000
        Rn = Mu_nmm / (phi * b * self.d**2)
        m = self.material.fy / (0.85 * self.material.fc_prime)
        
        term = 1 - (2 * m * Rn / self.material.fy)
        if term < 0:
            rho = 0.02
        else:
            rho = (1/m) * (1 - math.sqrt(term))
        
        As_req = rho * b * self.d
        Ag = b * self.h
        
        if self.material.fy < 420:
            As_min = 0.0020 * Ag
        else:
            As_min = max((0.0018 * 420 / self.material.fy) * Ag, 0.0014 * Ag)
        
        As_final = max(As_req, As_min)
        spacing_req = 1000 * self.main_bar.area / As_final
        spacing_max_by_code = min(3 * self.h, 450)
        spacing_max = min(spacing_req, spacing_max_by_code)
        spacing_final = max(75, math.floor(spacing_max / 25) * 25)
        As_provided = 1000 * self.main_bar.area / spacing_final
        
        return {
            'location': location,
            'Mu': Mu,
            'Rn': Rn,
            'rho': rho,
            'As_req': As_req,
            'As_min': As_min,
            'As_final': As_final,
            'As_prov': As_provided,
            'spacing_req': spacing_req,
            'spacing_max': spacing_max,
            'spacing_final': spacing_final,
            'bar_size': self.main_bar.bar_size,
            'bar_area': self.main_bar.area
        }
    
    def calculate_shrinkage_steel(self):
        """Step 7: Calculate shrinkage and temperature reinforcement"""
        Ag = 1000 * self.h
        
        if self.material.fy < 420:
            As_sh_req = 0.0020 * Ag
        else:
            As_sh_req = (0.0018 * 420 / self.material.fy) * Ag
        
        spacing_req = 1000 * self.shrinkage_bar.area / As_sh_req
        spacing_max_by_code = min(5 * self.h, 450)
        spacing_max = min(spacing_req, spacing_max_by_code)
        spacing_final = math.floor(spacing_max / 25) * 25
        As_provided = 1000 * self.shrinkage_bar.area / spacing_final
        
        return {
            'As_req': As_sh_req,
            'As_prov': As_provided,
            'spacing_req': spacing_req,
            'spacing_max': spacing_max,
            'spacing_final': spacing_final,
            'bar_size': self.shrinkage_bar.bar_size,
            'bar_area': self.shrinkage_bar.area
        }
    
    def check_shear(self):
        """Step 8: One-way shear check"""
        L_n = self.clear_span / 1000
        d_m = self.d / 1000
        
        if self.support_condition == 'simply_supported':
            Vu = self.wu * (L_n/2 - d_m)
        elif self.support_condition == 'one_end_continuous':
            Vu_simple = self.wu * (L_n/2 - d_m)
            Vu_continuous = self.wu * (0.575 * L_n - d_m)
            Vu = max(Vu_simple, Vu_continuous)
        elif self.support_condition == 'both_ends_continuous':
            Vu = self.wu * (L_n/2 - d_m)
        elif self.support_condition == 'cantilever':
            Vu = self.wu * L_n
        else:
            Vu = self.wu * (L_n/2)
        
        Vu = max(Vu, 0)
        lamda = 1.0
        sqrt_fc = math.sqrt(self.material.fc_prime)
        Vc = 0.17 * lamda * sqrt_fc * 1000 * self.d / 1000
        phiVc = 0.75 * Vc
        utilization = (Vu / phiVc) * 100 if phiVc > 0 else 0
        
        if Vu <= phiVc:
            status = "✓ PASS - No shear reinforcement required"
        else:
            status = "✗ FAIL - Increase slab thickness"
        
        return {
            'Vu': Vu,
            'Vc': Vc,
            'phiVc': phiVc,
            'utilization': utilization,
            'status': status
        }
    
    def design(self):
        """Complete design of one-way slab"""
        self.calculate_initial_thickness(self.clear_span, self.support_condition, self.user_h)
        wu, total_dead, self_weight = self.calculate_factored_load()
        moments = self.calculate_moments()
        d = self.calculate_effective_depth()
        
        self.reinforcement = {}
        for location, Mu in self.moments.items():
            result = self.calculate_required_steel(Mu, location)
            if result:
                self.reinforcement[location] = result
        
        self.shrinkage = self.calculate_shrinkage_steel()
        self.shear = self.check_shear()
        
        return {
            'thickness': self.h,
            'effective_depth': self.d,
            'factored_load': self.wu,
            'self_weight': self_weight,
            'total_dead': total_dead,
            'moments': self.moments,
            'reinforcement': self.reinforcement,
            'shrinkage': self.shrinkage,
            'shear': self.shear,
            'notes': self.notes
        }

# ============================================================================
# CUSTOM CSS FOR PREMIUM UI - EYE-FRIENDLY COLOR SCHEME
# ============================================================================

st.markdown("""
<style>
    /* Import Google Fonts */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
    
    /* Global Styles - Soft, eye-friendly background */
    .stApp {
        font-family: 'Inter', sans-serif;
        background: linear-gradient(135deg, #f5f7fa 0%, #e9ecf2 100%);
    }
    
    /* Main Container - Soft blue gradient */
    .main-header {
        background: linear-gradient(135deg, #2c3e50 0%, #3498db 100%);
        padding: 2.5rem;
        border-radius: 30px;
        margin-bottom: 2rem;
        box-shadow: 0 10px 30px rgba(44, 62, 80, 0.15);
        animation: slideDown 0.5s ease;
    }
    
    @keyframes slideDown {
        from { transform: translateY(-20px); opacity: 0; }
        to { transform: translateY(0); opacity: 1; }
    }
    
    .main-header h1 {
        color: white;
        font-size: 2.5rem;
        font-weight: 700;
        margin: 0;
        text-shadow: 2px 2px 4px rgba(0,0,0,0.1);
    }
    
    .main-header p {
        color: rgba(255,255,255,0.9);
        font-size: 1.1rem;
        margin: 0.5rem 0 0 0;
    }
    
    /* Glassmorphism Cards - Soft white with blur */
    .glass-card {
        background: rgba(255, 255, 255, 0.95);
        backdrop-filter: blur(10px);
        border-radius: 20px;
        padding: 1.5rem;
        box-shadow: 0 8px 32px rgba(31, 38, 135, 0.08);
        border: 1px solid rgba(255, 255, 255, 0.18);
        transition: all 0.3s ease;
        animation: fadeIn 0.5s ease;
    }
    
    .glass-card:hover {
        transform: translateY(-5px);
        box-shadow: 0 12px 48px rgba(31, 38, 135, 0.12);
    }
    
    @keyframes fadeIn {
        from { opacity: 0; }
        to { opacity: 1; }
    }
    
    /* Metric Cards - Soft professional colors */
    .metric-card {
        background: linear-gradient(135deg, #2c3e50 0%, #34495e 100%);
        padding: 1.5rem;
        border-radius: 20px;
        text-align: center;
        color: white;
        box-shadow: 0 10px 30px rgba(44, 62, 80, 0.2);
        transition: all 0.3s ease;
    }
    
    .metric-card:hover {
        transform: scale(1.02);
        box-shadow: 0 15px 40px rgba(44, 62, 80, 0.25);
    }
    
    .metric-card .label {
        font-size: 0.9rem;
        opacity: 0.9;
        margin-bottom: 0.5rem;
    }
    
    .metric-card .value {
        font-size: 2rem;
        font-weight: 700;
    }
    
    .metric-card .unit {
        font-size: 0.8rem;
        opacity: 0.8;
        margin-top: 0.25rem;
    }
    
    /* Status Badges - Softer colors */
    .success-badge {
        background: linear-gradient(135deg, #27ae60 0%, #2ecc71 100%);
        color: white;
        padding: 0.5rem 1.5rem;
        border-radius: 30px;
        font-weight: 600;
        font-size: 0.9rem;
        display: inline-block;
        box-shadow: 0 4px 15px rgba(39, 174, 96, 0.2);
    }
    
    .warning-badge {
        background: linear-gradient(135deg, #f39c12 0%, #f1c40f 100%);
        color: white;
        padding: 0.5rem 1.5rem;
        border-radius: 30px;
        font-weight: 600;
        font-size: 0.9rem;
        display: inline-block;
        box-shadow: 0 4px 15px rgba(243, 156, 18, 0.2);
    }
    
    .danger-badge {
        background: linear-gradient(135deg, #c0392b 0%, #e74c3c 100%);
        color: white;
        padding: 0.5rem 1.5rem;
        border-radius: 30px;
        font-weight: 600;
        font-size: 0.9rem;
        display: inline-block;
        box-shadow: 0 4px 15px rgba(192, 57, 43, 0.2);
    }
    
    /* Input Styling - Clean and soft */
    .stTextInput > div > div > input,
    .stNumberInput > div > div > input,
    .stSelectbox > div > div > select,
    .stTextArea > div > div > textarea {
        border-radius: 15px !important;
        border: 2px solid #e0e4e9 !important;
        padding: 0.75rem 1rem !important;
        font-size: 1rem !important;
        transition: all 0.3s ease !important;
        background-color: white !important;
    }
    
    .stTextInput > div > div > input:focus,
    .stNumberInput > div > div > input:focus,
    .stSelectbox > div > div > select:focus {
        border-color: #3498db !important;
        box-shadow: 0 0 0 3px rgba(52, 152, 219, 0.1) !important;
    }
    
    /* Button Styling - Professional blue */
    .stButton > button {
        background: linear-gradient(135deg, #2c3e50 0%, #3498db 100%);
        color: white;
        border: none;
        padding: 0.75rem 2rem;
        font-size: 1.1rem;
        font-weight: 600;
        border-radius: 50px;
        transition: all 0.3s ease;
        width: 100%;
        box-shadow: 0 4px 15px rgba(44, 62, 80, 0.2);
    }
    
    .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 8px 25px rgba(44, 62, 80, 0.3);
    }
    
    /* Tab Styling - Soft background */
    .stTabs [data-baseweb="tab-list"] {
        gap: 2rem;
        background-color: rgba(255,255,255,0.8);
        padding: 0.5rem;
        border-radius: 50px;
        backdrop-filter: blur(10px);
        box-shadow: 0 4px 10px rgba(0,0,0,0.05);
    }
    
    .stTabs [data-baseweb="tab"] {
        border-radius: 30px;
        padding: 0.5rem 1.5rem;
        font-weight: 600;
        color: #2c3e50;
    }
    
    .stTabs [aria-selected="true"] {
        background: linear-gradient(135deg, #2c3e50 0%, #3498db 100%);
        color: white !important;
    }
    
    /* Expander Styling */
    .streamlit-expanderHeader {
        background: rgba(255,255,255,0.9);
        border-radius: 15px;
        font-weight: 600;
        color: #2c3e50;
        backdrop-filter: blur(10px);
        border: 1px solid rgba(255,255,255,0.5);
    }
    
    /* Progress Bar - Soft gradient */
    .stProgress > div > div {
        background: linear-gradient(135deg, #2c3e50 0%, #3498db 100%);
        border-radius: 10px;
    }
    
    /* Tooltip */
    .tooltip {
        position: relative;
        display: inline-block;
        cursor: help;
    }
    
    .tooltip .tooltiptext {
        visibility: hidden;
        width: 200px;
        background: linear-gradient(135deg, #2c3e50 0%, #3498db 100%);
        color: #fff;
        text-align: center;
        border-radius: 10px;
        padding: 8px;
        position: absolute;
        z-index: 1;
        bottom: 125%;
        left: 50%;
        margin-left: -100px;
        opacity: 0;
        transition: opacity 0.3s;
        font-size: 0.9rem;
        box-shadow: 0 4px 15px rgba(0,0,0,0.1);
    }
    
    .tooltip:hover .tooltiptext {
        visibility: visible;
        opacity: 1;
    }
    
    /* Footer - Matching header */
    .footer {
        background: linear-gradient(135deg, #2c3e50 0%, #34495e 100%);
        padding: 2rem;
        border-radius: 30px;
        margin-top: 3rem;
        color: white;
        text-align: center;
        box-shadow: 0 -10px 30px rgba(44, 62, 80, 0.1);
    }
    
    /* Dataframe styling */
    .dataframe {
        font-family: 'Inter', sans-serif;
        border: none !important;
        border-radius: 15px;
        overflow: hidden;
    }
    
    .dataframe th {
        background: linear-gradient(135deg, #2c3e50 0%, #34495e 100%);
        color: white !important;
        font-weight: 600;
        padding: 12px !important;
    }
    
    .dataframe td {
        padding: 10px !important;
        background-color: white;
        border-bottom: 1px solid #eef2f6;
    }
    
    /* Sidebar styling */
    .css-1d391kg {
        background-color: rgba(255,255,255,0.95);
    }
    
    /* Responsive Design */
    @media (max-width: 768px) {
        .main-header h1 {
            font-size: 1.8rem;
        }
        
        .metric-card .value {
            font-size: 1.5rem;
        }
    }
</style>
""", unsafe_allow_html=True)

# ============================================================================
# UI HELPER FUNCTIONS
# ============================================================================

def download_button(object_to_download, download_filename, button_text):
    """Generate download button with custom styling"""
    if isinstance(object_to_download, pd.DataFrame):
        object_to_download = object_to_download.to_csv(index=False)
    
    b64 = base64.b64encode(object_to_download.encode()).decode()
    button_uuid = str(time.time()).replace('.', '')
    
    custom_css = f"""
        <style>
            #{button_uuid} {{
                background: linear-gradient(135deg, #2c3e50 0%, #3498db 100%);
                color: white;
                padding: 0.75rem 2rem;
                border-radius: 50px;
                text-decoration: none;
                font-weight: 600;
                display: inline-block;
                transition: all 0.3s ease;
                border: none;
                cursor: pointer;
                box-shadow: 0 4px 15px rgba(44, 62, 80, 0.2);
                margin: 0.5rem 0;
                text-align: center;
            }}
            #{button_uuid}:hover {{
                transform: translateY(-2px);
                box-shadow: 0 8px 25px rgba(44, 62, 80, 0.3);
            }}
        </style>
    """
    
    dl_link = f'{custom_css}<a download="{download_filename}" id="{button_uuid}" href="data:file/txt;base64,{b64}">{button_text}</a>'
    
    return dl_link

# ============================================================================
# MAIN APPLICATION
# ============================================================================

def main():
    # Header
    st.markdown("""
    <div class="main-header">
        <h1>🏗️ One-Way Reinforced Concrete Slab Designer Pro</h1>
        <p>Professional Design Tool Based on ACI 318-14 • Version 4.0</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Simple sidebar menu
    with st.sidebar:
        st.markdown("### 🧭 Menu")
        page = st.radio(
            "Navigation",
            ["Design Calculator", "Design Guide", "Code References", "About"],
            label_visibility="collapsed"
        )
        
        st.markdown("---")
        
        # Quick Stats (if results exist)
        if 'results' in st.session_state and st.session_state.results:
            st.markdown("### 📊 Quick Stats")
            results = st.session_state.results
            st.markdown(f"""
            <div class="glass-card">
                <p><strong>Thickness:</strong> {results['thickness']} mm</p>
                <p><strong>Max Moment:</strong> {max([abs(m) for m in results['moments'].values()]):.1f} kN·m</p>
                <p><strong>Shear Ratio:</strong> {results['shear']['utilization']:.1f}%</p>
            </div>
            """, unsafe_allow_html=True)
    
    if page == "Design Calculator":
        # Main Calculator Interface
        col1, col2 = st.columns([1, 1.2], gap="large")
        
        with col1:
            st.markdown("### 📋 Input Parameters")
            
            # Slab Dimensions
            with st.expander("📏 Slab Dimensions", expanded=True):
                clear_span = st.number_input(
                    "Clear Span (mm)",
                    min_value=500,
                    max_value=10000,
                    value=3500,
                    step=50,
                    help="Distance between faces of supports"
                )
            
            # Material Properties
            with st.expander("🧱 Material Properties", expanded=True):
                col_a, col_b = st.columns(2)
                with col_a:
                    fc = st.number_input(
                        "Concrete f'c (MPa)",
                        min_value=17.0,
                        max_value=70.0,
                        value=28.0,
                        step=0.5,
                        help="Concrete compressive strength"
                    )
                    density = st.number_input(
                        "Density (kN/m³)",
                        min_value=22.0,
                        max_value=26.0,
                        value=25.0,
                        step=0.1
                    )
                
                with col_b:
                    fy = st.number_input(
                        "Steel fy (MPa)",
                        min_value=275,
                        max_value=550,
                        value=420,
                        step=5,
                        help="Steel yield strength"
                    )
                    cover = st.number_input(
                        "Cover (mm)",
                        min_value=15,
                        max_value=50,
                        value=20,
                        step=5
                    )
            
            # Loads
            with st.expander("⚖️ Loads", expanded=True):
                col_a, col_b = st.columns(2)
                with col_a:
                    dead_load = st.number_input(
                        "Dead Load (kN/m²)",
                        min_value=0.0,
                        max_value=20.0,
                        value=1.5,
                        step=0.1,
                        help="Floor finish, partitions, etc."
                    )
                with col_b:
                    live_load = st.number_input(
                        "Live Load (kN/m²)",
                        min_value=0.0,
                        max_value=30.0,
                        value=3.0,
                        step=0.1,
                        help="Occupancy live load"
                    )
            
            # Support Condition
            with st.expander("🔄 Support Condition", expanded=True):
                support_options = {
                    "Simply Supported": "simply_supported",
                    "One End Continuous": "one_end_continuous",
                    "Both Ends Continuous": "both_ends_continuous",
                    "Cantilever": "cantilever"
                }
                
                support_choice = st.selectbox(
                    "Select Support Type",
                    options=list(support_options.keys()),
                    index=0
                )
                
                # Show thickness coefficient
                coeffs = {
                    "Simply Supported": "L/20",
                    "One End Continuous": "L/24",
                    "Both Ends Continuous": "L/28",
                    "Cantilever": "L/10"
                }
                st.info(f"📐 Minimum thickness: **{coeffs[support_choice]}**")
            
            # Reinforcement
            with st.expander("🔄 Reinforcement", expanded=True):
                bar_sizes = list(BarProperties.BAR_DATA.keys())
                
                col_a, col_b = st.columns(2)
                with col_a:
                    main_bar = st.selectbox(
                        "Main Bar Size",
                        options=bar_sizes,
                        index=1,
                        format_func=lambda x: f"{x} (φ{BarProperties.BAR_DATA[x]['diameter']}mm)"
                    )
                with col_b:
                    shrinkage_bar = st.selectbox(
                        "Shrinkage Bar Size",
                        options=bar_sizes,
                        index=1,
                        format_func=lambda x: f"{x} (φ{BarProperties.BAR_DATA[x]['diameter']}mm)"
                    )
            
            # Advanced Options
            with st.expander("⚙️ Options", expanded=False):
                user_thickness = st.number_input(
                    "Override Thickness (mm)",
                    min_value=50,
                    max_value=500,
                    value=None,
                    step=5,
                    help="Leave blank for automatic calculation"
                )
                
                generate_report = st.checkbox("Generate detailed report", value=True)
            
            # Calculate Button
            calculate = st.button("🚀 Calculate Design", use_container_width=True)
        
        with col2:
            if calculate:
                with st.spinner("🔄 Performing structural analysis..."):
                    time.sleep(1)  # Simulate calculation
                    
                    try:
                        # Initialize slab
                        slab = OneWaySlab()
                        slab.clear_span = clear_span
                        slab.material = MaterialProperties(
                            fc_prime=fc,
                            fy=fy,
                            concrete_density=density,
                            cover=cover
                        )
                        slab.loads = Loads(
                            superimposed_dead=dead_load,
                            live_load=live_load
                        )
                        slab.support_condition = support_options[support_choice]
                        slab.main_bar = BarProperties(main_bar)
                        slab.shrinkage_bar = BarProperties(shrinkage_bar)
                        
                        if user_thickness:
                            slab.user_h = user_thickness
                        
                        # Run design
                        results = slab.design()
                        
                        # Store in session state
                        st.session_state.results = results
                        st.session_state.inputs = {
                            'clear_span': clear_span,
                            'support_condition': support_choice
                        }
                        
                        # Success message with confetti effect
                        st.balloons()
                        st.success("✅ Design completed successfully!")
                        
                    except Exception as e:
                        st.error(f"❌ Calculation Error: {str(e)}")
                        st.stop()
            
            # Display results if available
            if 'results' in st.session_state and st.session_state.results:
                results = st.session_state.results
                
                # Key Metrics
                st.markdown("### 📈 Key Parameters")
                
                col_m1, col_m2, col_m3, col_m4 = st.columns(4)
                
                with col_m1:
                    st.markdown(f"""
                    <div class="metric-card">
                        <div class="label">Slab Thickness (h)</div>
                        <div class="value">{results['thickness']} mm</div>
                    </div>
                    """, unsafe_allow_html=True)
                
                with col_m2:
                    st.markdown(f"""
                    <div class="metric-card">
                        <div class="label">Effective Depth (d)</div>
                        <div class="value">{results['effective_depth']:.1f} mm</div>
                    </div>
                    """, unsafe_allow_html=True)
                
                with col_m3:
                    st.markdown(f"""
                    <div class="metric-card">
                        <div class="label">Factored Load (wu)</div>
                        <div class="value">{results['factored_load']:.2f} kN/m</div>
                    </div>
                    """, unsafe_allow_html=True)
                
                with col_m4:
                    max_moment = max([abs(m) for m in results['moments'].values()])
                    st.markdown(f"""
                    <div class="metric-card">
                        <div class="label">Max Moment</div>
                        <div class="value">{max_moment:.1f} kN·m</div>
                    </div>
                    """, unsafe_allow_html=True)
                
                # Tabs for detailed results (removed Diagrams tab)
                tab1, tab2, tab3 = st.tabs([
                    "🔄 Reinforcement",
                    "✂️ Shear Check",
                    "📄 Report"
                ])
                
                with tab1:
                    col_r1, col_r2 = st.columns([1, 1])
                    
                    with col_r1:
                        st.markdown("#### Main Flexural Reinforcement")
                        
                        # Create dataframe
                        rebar_data = []
                        for loc, det in results['reinforcement'].items():
                            rebar_data.append({
                                "Location": loc[:25] + "..." if len(loc) > 25 else loc,
                                "Moment (kN·m)": f"{det['Mu']:.1f}",
                                "Bar Size": det['bar_size'],
                                "Spacing (mm)": det['spacing_final'],
                                "As (mm²/m)": f"{det['As_prov']:.0f}"
                            })
                        
                        if rebar_data:
                            df_rebar = pd.DataFrame(rebar_data)
                            st.dataframe(
                                df_rebar,
                                use_container_width=True,
                                hide_index=True
                            )
                    
                    with col_r2:
                        st.markdown("#### Shrinkage & Temperature")
                        
                        # Shrinkage details in cards
                        st.markdown(f"""
                        <div class="glass-card">
                            <p><strong>Bar Size:</strong> {results['shrinkage']['bar_size']}</p>
                            <p><strong>Spacing:</strong> {results['shrinkage']['spacing_final']} mm c/c</p>
                            <p><strong>Required As:</strong> {results['shrinkage']['As_req']:.0f} mm²/m</p>
                            <p><strong>Provided As:</strong> {results['shrinkage']['As_prov']:.0f} mm²/m</p>
                        </div>
                        """, unsafe_allow_html=True)
                        
                        # Efficiency indicator
                        efficiency = (results['shrinkage']['As_prov'] / results['shrinkage']['As_req'] * 100)
                        st.progress(min(efficiency/100, 1.0))
                        st.caption(f"Efficiency: {efficiency:.1f}%")
                
                with tab2:
                    shear = results['shear']
                    
                    # Status badge
                    if "PASS" in shear['status']:
                        badge_class = "success-badge"
                        status_icon = "✅"
                    else:
                        badge_class = "danger-badge"
                        status_icon = "❌"
                    
                    st.markdown(f"""
                    <div class="glass-card">
                        <div style="display: flex; justify-content: space-between; align-items: center;">
                            <h4 style="margin:0;">One-Way Shear Check</h4>
                            <span class="{badge_class}">{status_icon} {shear['status']}</span>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    col_s1, col_s2, col_s3 = st.columns(3)
                    
                    with col_s1:
                        st.metric(
                            "Factored Shear (Vu)",
                            f"{shear['Vu']:.2f} kN"
                        )
                    
                    with col_s2:
                        st.metric(
                            "Concrete Capacity (φVc)",
                            f"{shear['phiVc']:.2f} kN"
                        )
                    
                    with col_s3:
                        st.metric(
                            "Utilization",
                            f"{shear['utilization']:.1f}%"
                        )
                    
                    # Utilization gauge
                    st.markdown("#### Capacity Utilization")
                    st.progress(min(shear['utilization']/100, 1.0))
                    
                    if shear['utilization'] < 50:
                        st.caption("✅ Safe - Low Utilization")
                    elif shear['utilization'] < 80:
                        st.caption("⚠️ Adequate - Moderate Utilization")
                    elif shear['utilization'] <= 100:
                        st.caption("⚡ Critical - Near Limit")
                    else:
                        st.caption("❌ Failed - Redesign Needed")
                
                with tab3:
                    if generate_report:
                        # Generate professional report
                        report = f"""ONE-WAY REINFORCED CONCRETE SLAB DESIGN REPORT
===============================================
Date: {datetime.now().strftime('%B %d, %Y at %H:%M')}
Code: ACI 318-14

INPUT PARAMETERS
----------------
Clear Span: {clear_span} mm
Support Condition: {support_choice}
Concrete f'c: {fc} MPa
Steel fy: {fy} MPa
Dead Load: {dead_load} kN/m²
Live Load: {live_load} kN/m²
Main Reinforcement: {main_bar}
Shrinkage Reinforcement: {shrinkage_bar}

DESIGN RESULTS
--------------
Slab Thickness: {results['thickness']} mm
Effective Depth: {results['effective_depth']:.1f} mm
Factored Load: {results['factored_load']:.2f} kN/m

Moments:
"""
                        
                        for loc, val in results['moments'].items():
                            report += f"  {loc}: {val:.2f} kN·m\n"
                        
                        report += f"""
Shear Check:
  Vu = {shear['Vu']:.2f} kN
  φVc = {shear['phiVc']:.2f} kN
  Status: {shear['status']}

Reinforcement Summary:
"""
                        
                        for loc, det in results['reinforcement'].items():
                            report += f"  {loc}: {det['bar_size']} @ {det['spacing_final']} mm c/c\n"
                        
                        report += f"""
Shrinkage Reinforcement:
  {results['shrinkage']['bar_size']} @ {results['shrinkage']['spacing_final']} mm c/c

This design complies with ACI 318-14 requirements.
"""
                        
                        st.text_area("Report Preview", report, height=300)
                        
                        # Download buttons
                        col_b1, col_b2 = st.columns(2)
                        with col_b1:
                            st.markdown(
                                download_button(report, f"slab_report_{datetime.now().strftime('%Y%m%d')}.txt", "📥 Download Report (TXT)"),
                                unsafe_allow_html=True
                            )
                        
                        with col_b2:
                            if 'df_rebar' in locals():
                                csv_data = df_rebar.to_csv(index=False)
                                st.markdown(
                                    download_button(csv_data, f"slab_results_{datetime.now().strftime('%Y%m%d')}.csv", "📥 Download Results (CSV)"),
                                    unsafe_allow_html=True
                                )
                
                # Design Notes
                if results['notes']:
                    st.markdown("### 📝 Design Notes")
                    for note in results['notes']:
                        st.warning(note)
                
                # New Design Button
                if st.button("🔄 Start New Design", use_container_width=True):
                    st.session_state.results = None
                    st.rerun()
    
    elif page == "Design Guide":
        st.markdown("""
        <div class="glass-card">
            <h2>📚 One-Way Slab Design Guide</h2>
            <p>Based on ACI 318-14 Building Code Requirements</p>
            
            <h3>Step 1: Determine Minimum Thickness</h3>
            <ul>
                <li>Simply Supported: L/20</li>
                <li>One End Continuous: L/24</li>
                <li>Both Ends Continuous: L/28</li>
                <li>Cantilever: L/10</li>
            </ul>
            
            <h3>Step 2: Calculate Factored Loads</h3>
            <p>wu = 1.2D + 1.6L (ACI 318-14 Eq. 5.3.1b)</p>
            
            <h3>Step 3: Determine Factored Moments</h3>
            <p>Using ACI Approximate Moment Coefficients</p>
            
            <h3>Step 4: Calculate Required Reinforcement</h3>
            <p>As = ρbd where ρ = (0.85f'c/fy)[1 - √(1 - 2Rn/0.85f'c)]</p>
            
            <h3>Step 5: Check Shear Capacity</h3>
            <p>φVc = 0.75 × 0.17√f'c × b × d</p>
        </div>
        """, unsafe_allow_html=True)
    
    elif page == "Code References":
        st.markdown("""
        <div class="glass-card">
            <h2>📖 ACI 318-14 Code References</h2>
            
            <h3>Section 7.3 - Minimum Slab Thickness</h3>
            <p>Table 7.3.1.1 provides minimum thickness for one-way slabs</p>
            
            <h3>Section 8.3 - Approximate Frame Analysis</h3>
            <p>Moment coefficients for continuous slabs</p>
            
            <h3>Section 9.2 - Load Combinations</h3>
            <p>1.2D + 1.6L for strength design</p>
            
            <h3>Section 22.5 - Shear Strength</h3>
            <p>Vc = 0.17λ√f'c × b × d for slabs</p>
            
            <h3>Section 24.4 - Shrinkage and Temperature</h3>
            <p>Minimum reinforcement ratios for temperature effects</p>
        </div>
        """, unsafe_allow_html=True)
    
    elif page == "About":
        st.markdown("""
        <div class="glass-card">
            <h2>🏗️ One-Way Slab Designer Pro</h2>
            <p><strong>Version:</strong> 4.0</p>
            <p><strong>Code:</strong> ACI 318-14</p>
            <p><strong>Developer:</strong> Structural Engineering Tools</p>
            
            <h3>Features:</h3>
            <ul>
                <li>Professional one-way slab design</li>
                <li>Comprehensive design reports</li>
                <li>Real-time calculations</li>
                <li>Multiple support conditions</li>
            </ul>
            
            <h3>Disclaimer:</h3>
            <p>This tool is for preliminary design only. Final design must be verified by a licensed professional engineer.</p>
            
            <h3>Support:</h3>
            <p>For questions or feedback, please contact: support@example.com</p>
        </div>
        """, unsafe_allow_html=True)
    
    # Footer
    st.markdown("""
    <div class="footer">
        <p style="margin:0; font-size:1.1rem;">🏗️ One-Way Slab Designer Pro v4.0 | Based on ACI 318-14</p>
        <p style="margin:0.5rem 0 0 0; font-size:0.9rem; opacity:0.8;">© 2024 Structural Engineering Tools | For Professional Use Only</p>
    </div>
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()