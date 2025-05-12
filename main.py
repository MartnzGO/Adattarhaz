# main.py

import sys
import sqlite3
import pandas as pd
from pandas.errors import ParserError
import tkinter as tk
from tkinter import ttk, Menu, filedialog, Spinbox # Spinbox tk-ból jön
from PIL import Image, ImageTk
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib.pyplot as plt
import os # Képbetöltéshez

# --- Machine Learning Imports ---
# Csak akkor importáljuk, ha tényleg használjuk (pl. az AIFrame-ben)
# from sklearn.linear_model import LinearRegression
# from sklearn.preprocessing import PolynomialFeatures
# from sklearn.pipeline import make_pipeline
# import numpy as np
# --> Importáljuk őket az AIFrame class definíciója elé vagy a run_prediction-be helyileg

DB_PATH = "ecommerce_dwh.sqlite"
QUERIES = {
    "Monthly Revenue": """
        SELECT d.year || '-' || printf('%02d', d.month) AS x, /* YYYY-MM format */
               SUM(f.total_amount) AS y
        FROM Fact_Sales f
        JOIN Dim_Date d ON f.date_key = d.date_key
        GROUP BY d.year, d.month
        ORDER BY d.year, d.month;
    """,
    "Top 10 Categories by Revenue": """
        SELECT COALESCE(p.product_category_name, 'Unknown') AS x, /* Handle NULLs */
               SUM(f.total_amount) AS y
        FROM Fact_Sales f
        JOIN Dim_Product p ON f.product_key = p.product_key
        WHERE p.product_category_name IS NOT NULL AND p.product_category_name != '' AND LENGTH(p.product_category_name) > 1
        GROUP BY COALESCE(p.product_category_name, 'Unknown')
        ORDER BY y DESC
        LIMIT 10;
    """,
    "Orders Count by State": """
        SELECT c.state AS x,
               COUNT(DISTINCT f.order_id) AS y /* Count distinct orders */
        FROM Fact_Sales f
        JOIN Dim_Customer c ON f.customer_key = c.customer_key
        GROUP BY c.state
        ORDER BY y DESC
        LIMIT 15; /* Show more states */
    """,
    "Payment Type Distribution": """
        SELECT p.payment_type AS x,
               COUNT(DISTINCT f.order_id) AS y /* Count distinct orders per payment type */
        FROM Fact_Sales f
        JOIN Dim_Payment p ON f.payment_key = p.payment_key
        WHERE p.payment_type IS NOT NULL AND p.payment_type != 'not_defined' /* Filter out undefined */
        GROUP BY p.payment_type
        ORDER BY y DESC;
    """
}


class MainApplication(tk.Tk):
    def __init__(self):
        super().__init__()
        # --- Basic Setup ---
        self.title("📊 E-Commerce DWH Dashboard")
        self.geometry("950x700") # Default size
        # Set minimum size to prevent squishing widgets too much
        self.minsize(750, 550)
        self.protocol("WM_DELETE_WINDOW", self.on_close)

        # --- Styling Setup (Early) ---
        self.style = ttk.Style(self)
        # Choose a theme that works well cross-platform (clam, alt, default, classic)
        # 'clam' often looks good and is widely available
        available_themes = self.style.theme_names()
        # print("Available themes:", available_themes) # Uncomment to see themes on your system
        preferred_theme = 'clam' if 'clam' in available_themes else 'default'
        try:
            self.style.theme_use(preferred_theme)
        except tk.TclError:
             print(f"Warning: Theme '{preferred_theme}' not found, using default.")
             self.style.theme_use('default')


        # --- Layout ---
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        container = ttk.Frame(self)
        container.grid(row=0, column=0, sticky="nsew")
        container.columnconfigure(0, weight=1)
        container.rowconfigure(0, weight=1)

        # --- Frame Creation ---
        self.frames = {}
        for F in (MenuFrame, AnalysisFrame, AIFrame):
            frame = F(parent=container, controller=self)
            self.frames[F.__name__] = frame
            frame.grid(row=0, column=0, sticky="nsew")

        # --- Theme Initialization ---
        # Initialize themes after frames are created, AnalysisFrame drives the definitions
        if "AnalysisFrame" in self.frames:
             self.frames["AnalysisFrame"]._create_styles_and_apply_default_theme()
        if "AIFrame" in self.frames and "AnalysisFrame" in self.frames:
            analysis_frame = self.frames["AnalysisFrame"]
            self.frames["AIFrame"]._init_theme_settings(analysis_frame.current_mode,
                                                        analysis_frame.light_colors,
                                                        analysis_frame.dark_colors)

        # --- Start ---
        self.show_frame("MenuFrame")

    def on_close(self):
        # Close matplotlib figures explicitly to free resources
        for frame_instance in self.frames.values():
            # Check if attribute exists and is a valid figure before closing
            if hasattr(frame_instance, 'fig') and isinstance(getattr(frame_instance, 'fig', None), plt.Figure):
                plt.close(frame_instance.fig)
            if hasattr(frame_instance, 'fig_ai') and isinstance(getattr(frame_instance, 'fig_ai', None), plt.Figure):
                 plt.close(frame_instance.fig_ai)
        self.destroy()
        # sys.exit(0) # Often not needed, destroy() handles clean exit

    def get_current_theme_settings(self):
        """Helper to get current theme settings safely."""
        if "AnalysisFrame" in self.frames:
            analysis_frame = self.frames["AnalysisFrame"]
            # Ensure colors are initialized before returning
            if not analysis_frame.light_colors or not analysis_frame.dark_colors:
                 analysis_frame._create_styles_and_apply_default_theme()
            return analysis_frame.current_mode, analysis_frame.light_colors, analysis_frame.dark_colors
        # Fallback default theme colors if AnalysisFrame isn't ready
        return 'light', {'bg':'#f0f0f0', 'fg':'#000000', 'widget_bg': '#ffffff', 'button_bg':'#e0e0e0', 'button_fg':'#000000', 'accent':'#0078D7', 'plot_bg': '#fdfdfd'}, {}

    def show_frame(self, name):
        frame_to_show = self.frames.get(name)
        if not frame_to_show:
            print(f"Error: Frame '{name}' not found.")
            return

        mode, light_colors, dark_colors = self.get_current_theme_settings()

        # Ensure the frame being shown has the correct theme applied
        if hasattr(frame_to_show, 'set_mode'): # AnalysisFrame
             frame_to_show.set_mode(mode)
        elif hasattr(frame_to_show, 'set_mode_ai'): # AIFrame
             # AI frame needs base colors passed to its set_mode_ai
             frame_to_show.set_mode_ai(mode, light_colors, dark_colors)
        elif hasattr(frame_to_show, 'configure'): # Fallback for simple frames like MenuFrame
            frame_to_show.configure(style='TFrame') # Apply base TFrame style


        frame_to_show.tkraise()

class MenuFrame(ttk.Frame):
    # ... (MenuFrame változatlan) ...
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller

        self.columnconfigure(0, weight=1)
        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=0) # Title row
        self.rowconfigure(1, weight=1) # Button row

        # Add padding around the main frame content
        self.grid_configure(padx=10, pady=10)

        # Title Label
        title = ttk.Label(self, text="Welcome to E-Commerce Dashboard", font=("Segoe UI", 22, "bold"))
        # Center title using grid, add vertical padding
        title.grid(row=0, column=0, columnspan=2, pady=(30, 20), sticky="n")

        # Image Loading
        try:
            script_dir = os.path.dirname(os.path.abspath(__file__)) if '__file__' in globals() else "."
            self.normal_orig = Image.open(os.path.join(script_dir, "Normal.jpg"))
            self.ai_orig = Image.open(os.path.join(script_dir, "AI.jpg"))
        except FileNotFoundError:
            print("Warning: Image files (Normal.jpg, AI.jpg) not found.")
            self.normal_orig = None
            self.ai_orig = None
        except Exception as e:
             print(f"Warning: Error loading images - {e}")
             self.normal_orig = None
             self.ai_orig = None

        # Buttons with Images
        button_style = 'Menu.TButton'
        self.controller.style.configure(button_style, font=('Segoe UI', 12, 'bold'), padding=10)

        self.normal_btn = ttk.Button(self, text="Standard Analysis", compound="top", style=button_style,
                                     command=lambda: controller.show_frame("AnalysisFrame"))
        self.normal_btn.grid(row=1, column=0, sticky="nsew", padx=30, pady=20)
        if self.normal_orig: self.normal_btn.bind("<Configure>", self._resize_normal_image)

        self.ai_btn = ttk.Button(self, text="AI Revenue Predictor", compound="top", style=button_style,
                                 command=lambda: controller.show_frame("AIFrame"))
        self.ai_btn.grid(row=1, column=1, sticky="nsew", padx=30, pady=20)
        if self.ai_orig: self.ai_btn.bind("<Configure>", self._resize_ai_image)


    def _resize_image_for_button(self, event, original_image, button):
        if not original_image: return
        btn_w, btn_h = event.width, event.height
        text_h_estimate = 40
        img_max_h = max(btn_h - text_h_estimate, 10)
        img_max_w = max(btn_w - 20, 10)
        orig_w, orig_h = original_image.size
        if orig_w <= 0 or orig_h <= 0: return
        ratio = min(img_max_w / orig_w, img_max_h / orig_h)
        new_w, new_h = int(orig_w * ratio), int(orig_h * ratio)
        if new_w > 0 and new_h > 0:
            try:
                img_resized = original_image.resize((new_w, new_h), Image.Resampling.LANCZOS)
                photo = ImageTk.PhotoImage(img_resized)
                button.config(image=photo); button.image = photo
            except Exception as e: print(f"Resize/ImageTk Error: {e}"); button.config(image='')
        else: button.config(image='')

    def _resize_normal_image(self, event): self._resize_image_for_button(event, self.normal_orig, self.normal_btn)
    def _resize_ai_image(self, event): self._resize_image_for_button(event, self.ai_orig, self.ai_btn)


class AnalysisFrame(ttk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent, padding=10)
        self.controller = controller
        self.current_mode = 'light'
        self.light_colors = {}
        self.dark_colors = {}
        self.fig = None
        self.ax = None
        self.canvas = None

        # --- UI Layout ---
        top_bar = ttk.Frame(self); top_bar.pack(fill=tk.X, pady=(0,5))
        ttk.Button(top_bar, text="← Back to Menu", command=lambda: controller.show_frame("MenuFrame")).pack(side=tk.LEFT)
        theme_frame = ttk.Frame(top_bar); theme_frame.pack(side=tk.RIGHT)
        ttk.Label(theme_frame, text="Theme:").pack(side=tk.LEFT, padx=(10,2))
        self.light_button = ttk.Button(theme_frame, text="Light", command=lambda: self.set_mode('light'))
        self.light_button.pack(side=tk.LEFT, padx=2)
        self.dark_button = ttk.Button(theme_frame, text="Dark", command=lambda: self.set_mode('dark'))
        self.dark_button.pack(side=tk.LEFT, padx=2)

        controls = ttk.Frame(self); controls.pack(fill=tk.X, pady=5)
        ttk.Label(controls, text="Select Report:").pack(side=tk.LEFT)
        self.combo = ttk.Combobox(controls, values=list(QUERIES.keys()), state="readonly", width=35)
        if QUERIES: self.combo.current(0)
        self.combo.pack(side=tk.LEFT, padx=5)
        ttk.Button(controls, text="Run ▶", command=self.run_query).pack(side=tk.LEFT, padx=5)
        ttk.Button(controls, text="Save Plot 💾", command=self.save_plot).pack(side=tk.LEFT, padx=5)

        self.chart_frame_container = ttk.Frame(self, relief=tk.SUNKEN, borderwidth=1)
        self.chart_frame_container.pack(fill=tk.BOTH, expand=True, pady=(5,0))

        self.status = ttk.Label(self, text="Ready. Select a report and click Run.", relief=tk.SUNKEN, anchor=tk.W)
        self.status.pack(fill=tk.X, side=tk.BOTTOM, ipady=2)
        # Styles and canvas setup are deferred until _create_styles... is called


    def _setup_plot_canvas_if_needed(self):
        if self.canvas is None and hasattr(self, 'chart_frame_container'):
            self.fig, self.ax = plt.subplots(figsize=(6, 4))
            self.canvas = FigureCanvasTkAgg(self.fig, master=self.chart_frame_container)
            self.canvas_widget = self.canvas.get_tk_widget()
            self.canvas_widget.pack(fill=tk.BOTH, expand=True)
            # Apply theme only if colors are already defined
            if self.light_colors and self.dark_colors:
                self._apply_theme_to_plot(self.current_mode)

    def _create_styles_and_apply_default_theme(self):
        """Defines colors and applies the default theme."""
        self.style = self.controller.style # Use the main application style object
        self.light_colors = {'bg':'#f0f0f0', 'fg':'#000000', 'widget_bg': '#ffffff', 'button_bg':'#e0e0e0', 'button_fg':'#000000', 'accent':'#0078D7', 'plot_bg': '#ffffff'} # White plot bg for light
        self.dark_colors  = {'bg':'#2e2e2e', 'fg':'#ffffff', 'widget_bg': '#3c3c3c', 'button_bg':'#444444', 'button_fg':'#ffffff', 'accent':'#4db8ff', 'plot_bg': '#383838', # Slightly lighter dark plot bg
                             'spin_bg': '#3c3c3c', 'spin_fg': '#ffffff', 'spin_btn_bg': '#555555'}

        # Configure base styles that apply to all frames using ttk
        self.style.configure('TFrame', background=self.light_colors['bg'])
        self.style.configure('TLabel', background=self.light_colors['bg'], foreground=self.light_colors['fg'], font=('Segoe UI', 10))
        self.style.configure('TButton', font=('Segoe UI', 10), padding=5) # Base button font/padding
        self.style.configure('TCombobox', font=('Segoe UI', 10))
        self.style.configure('Bold.TLabel', font=('Segoe UI', 10, 'bold')) # For status bars

        # Apply the initial default theme (light)
        self.set_mode(self.current_mode)


    def _apply_theme_to_widgets(self, mode):
        """Applies theme colors to THIS frame's Tkinter widgets."""
        colors = self.light_colors if mode == 'light' else self.dark_colors

        # Configure root style for general background/foreground
        # Do this carefully, might affect other parts if not specific enough
        # self.style.configure('.', background=colors['bg'], foreground=colors['fg'])

        # Configure THIS frame's background
        self.configure(style='TFrame') # Ensure the main frame uses the TFrame style

        # Configure specific widget styles used within THIS frame
        self.style.configure('TFrame', background=colors['bg'])
        self.style.configure('TLabel', background=colors['bg'], foreground=colors['fg'])
        # Make sure status bar uses Bold.TLabel and gets correct colors
        self.style.configure('Bold.TLabel', background=colors['bg'], foreground=colors['fg'])
        self.status.configure(style='Bold.TLabel')

        # --- Refined Button Styling ---
        self.style.configure('TButton',
                             background=colors['button_bg'], foreground=colors['button_fg'],
                             bordercolor=colors['fg'], # Less contrast might be better: colors['button_bg']?
                             lightcolor=colors['button_bg'], darkcolor=colors['button_bg'])
        self.style.map('TButton',
                       background=[('active', colors['accent']), ('!disabled', colors['button_bg'])],
                       # Ensure foreground stays correct on active/disabled
                       foreground=[('active', colors['button_fg']), ('!disabled', colors['button_fg'])])

        # --- Refined Combobox Styling ---
        self.style.configure('TCombobox',
                             selectbackground=colors['accent'], # Background of selected item in list
                             selectforeground=colors['button_fg'], # Text color of selected item in list
                             fieldbackground=colors['widget_bg'], # Background of the entry part
                             background=colors['button_bg'],     # Background of the dropdown arrow button
                             foreground=colors['fg'],            # Text color in the entry part
                             arrowcolor=colors['fg'])
        # Map for readonly state (most common state here)
        self.style.map('TCombobox',
                       fieldbackground=[('readonly', colors['widget_bg'])],
                       foreground=[('readonly', colors['fg'])],
                       background=[('readonly', colors['button_bg'])]) # Arrow button bg


    def _apply_theme_to_plot(self, mode):
        """Applies theme colors to THIS frame's Matplotlib plot."""
        if not all([self.fig, self.ax, self.canvas]): return # Plot components must exist
        colors = self.light_colors if mode == 'light' else self.dark_colors
        plot_bg = colors.get('plot_bg', colors['widget_bg']) # Fallback to widget_bg if plot_bg not defined
        fg_col = colors['fg']
        bg_col = colors['bg']

        self.fig.patch.set_facecolor(bg_col)
        self.ax.set_facecolor(plot_bg)
        for spine in self.ax.spines.values(): spine.set_color(fg_col)
        self.ax.tick_params(axis='x', colors=fg_col, labelcolor=fg_col)
        self.ax.tick_params(axis='y', colors=fg_col, labelcolor=fg_col)
        self.ax.title.set_color(fg_col)
        if self.ax.get_xlabel(): self.ax.xaxis.label.set_color(fg_col)
        if self.ax.get_ylabel(): self.ax.yaxis.label.set_color(fg_col)
        legend = self.ax.get_legend()
        if legend:
            legend.get_frame().set_facecolor(bg_col)
            legend.get_frame().set_edgecolor(fg_col)
            for text in legend.get_texts(): text.set_color(fg_col)
        self.canvas.draw_idle()


    def set_mode(self, mode):
        """Sets the application mode (light/dark) and updates themes."""
        if mode not in ['light', 'dark']: return # Ignore invalid modes
        self.current_mode = mode

        # Apply theme to Tk widgets first
        self._apply_theme_to_widgets(mode)

        # Create/Apply theme to plot canvas
        self._setup_plot_canvas_if_needed() # Ensure canvas exists
        if self.canvas:
            self._apply_theme_to_plot(mode)

        # Update theme buttons state (Optional: disable the active theme button)
        if hasattr(self, 'light_button'):
            self.light_button.state(['disabled' if mode == 'light' else '!disabled'])
        if hasattr(self, 'dark_button'):
            self.dark_button.state(['disabled' if mode == 'dark' else '!disabled'])


        # Propagate theme change to AIFrame
        if "AIFrame" in self.controller.frames:
            ai_frame = self.controller.frames["AIFrame"]
            # Pass the authoritative color definitions
            ai_frame.set_mode_ai(mode, self.light_colors, self.dark_colors)


    def run_query(self):
        """Runs the selected SQL query and displays the plot."""
        self._setup_plot_canvas_if_needed()
        selected_report_name = self.combo.get()
        if not selected_report_name:
            self.status.config(text="Please select a report."); return

        self.status.config(text=f"Running: {selected_report_name}…"); self.update_idletasks()

        try:
            conn = sqlite3.connect(DB_PATH); conn.execute("PRAGMA query_only = ON;")
            df = pd.read_sql_query(QUERIES[selected_report_name], conn); conn.close()

            # --- Clear and Reset Axes ---
            self.ax.clear()
            self.ax.set_aspect('auto') # *** FIX: Reset aspect ratio BEFORE plotting ***
            self.ax.grid(False) # Turn off grid initially, enable specifically for plot types

            if df.empty:
                self.status.config(text=f"No data found for: {selected_report_name}")
                self.ax.text(0.5, 0.5, "No data available.", ha='center', va='center', transform=self.ax.transAxes,
                             color=self.light_colors.get('fg','#000000') if self.current_mode == 'light' else self.dark_colors.get('fg','#ffffff'))
                self._apply_theme_to_plot(self.current_mode); return

            # --- Plotting Logic ---
            x_data, y_data = df['x'], df['y']
            y_data = y_data.reset_index(drop=True)
            cmap = plt.get_cmap('viridis' if self.current_mode == 'light' else 'plasma') # viridis often looks good on light
            num_colors = max(len(x_data), 2)
            plot_colors_full = cmap(np.linspace(0.1, 0.9, num_colors)) # Avoid too light/dark ends
            plot_colors = plot_colors_full[:len(x_data)] if len(x_data) <= num_colors else plot_colors_full

            if "Distribution" in selected_report_name:
                explode_values = [0] * len(y_data)
                if not y_data.empty and y_data.max() > 0:
                     try: max_idx = y_data.idxmax(); explode_values[max_idx] = 0.1
                     except (ValueError, IndexError): pass
                self.ax.pie(y_data, labels=x_data, autopct='%1.1f%%', startangle=90, # Changed start angle
                            colors=plot_colors, pctdistance=0.85, explode=explode_values,
                            wedgeprops={'edgecolor': self.light_colors.get('bg') if self.current_mode == 'light' else self.dark_colors.get('bg'), 'linewidth': 1},
                            textprops={'color': self.light_colors.get('fg') if self.current_mode == 'light' else self.dark_colors.get('fg')})
                self.ax.axis('equal') # *** Keep this specific to pie chart ***
            elif "Categories" in selected_report_name or "State" in selected_report_name:
                bars = self.ax.bar(x_data, y_data, color=plot_colors)
                self.ax.set_xticks(range(len(x_data)))
                self.ax.set_xticklabels(x_data, rotation=45, ha="right", fontsize=9)
                self.ax.grid(axis='y', linestyle=':', alpha=0.6) # Only y-grid for bar charts
            else: # Line plot
                line_color = self.light_colors.get('accent') if self.current_mode == 'light' else self.dark_colors.get('accent')
                self.ax.plot(x_data, y_data, marker='o', linestyle='-', color=line_color, linewidth=2, markersize=5)
                tick_spacing = max(1, len(x_data) // 12)
                valid_indices = [i for i in range(0, len(x_data), tick_spacing) if i < len(x_data)]
                if valid_indices:
                    self.ax.set_xticks(valid_indices)
                    self.ax.set_xticklabels([x_data.iloc[i] for i in valid_indices], rotation=45, ha="right", fontsize=9)
                self.ax.grid(True, linestyle=':', alpha=0.6) # Full grid for line charts

            self.ax.set_title(selected_report_name, fontsize=14, weight='bold')
            self.ax.set_ylabel("Value", fontsize=10)
            self.fig.tight_layout(pad=1.5)
            self._apply_theme_to_plot(self.current_mode) # Apply theme colors to the finished plot
            self.status.config(text=f"Successfully displayed: {selected_report_name}")

        except sqlite3.Error as e: self.status.config(text=f"Database error: {e}"); print(f"SQL Error: {e}")
        except FileNotFoundError: self.status.config(text=f"Error: Database file '{DB_PATH}' not found.")
        except KeyError:
             s_name = locals().get('selected_report_name', 'Unknown')
             if s_name in QUERIES: self.status.config(text=f"Err processing data for '{s_name}'.")
             else: self.status.config(text=f"Error: Report query '{s_name}' not found.")
        except Exception as e:
            self.status.config(text=f"An unexpected error occurred: {e}"); import traceback; traceback.print_exc()


    def save_plot(self):
        # ... (save_plot változatlan) ...
        if self.canvas is None or not self.ax.has_data():
            self.status.config(text="No plot to save. Run a report first.")
            return
        try:
            file_path = filedialog.asksaveasfilename(
                defaultextension=".png",
                filetypes=[("PNG Image", "*.png"), ("JPEG Image", "*.jpg"), ("SVG Vector Image", "*.svg"), ("PDF Document", "*.pdf"), ("All Files", "*.*")],
                title="Save Plot As..."
            )
            if file_path:
                self.fig.savefig(file_path, facecolor=self.fig.get_facecolor(), dpi=150, bbox_inches='tight')
                self.status.config(text=f"Plot saved to {os.path.basename(file_path)}") # Show only filename
        except Exception as e:
            self.status.config(text=f"Error saving plot: {e}")
            print(f"Save plot error: {e}")


# ========================
#      AI Frame Class
# ========================
# Lazy import ML libraries only when AIFrame is instantiated or used
try:
    from sklearn.linear_model import LinearRegression
    from sklearn.preprocessing import PolynomialFeatures
    from sklearn.pipeline import make_pipeline
    import numpy as np
    _ML_LIBS_AVAILABLE = True
except ImportError:
    print("Warning: ML libraries (scikit-learn, numpy) not found. AI functionality disabled.")
    _ML_LIBS_AVAILABLE = False


class AIFrame(ttk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent, padding=15)
        self.controller = controller
        self.fig_ai = None
        self.ax_ai = None
        self.canvas_ai = None
        self.ai_chart_frame_container = None
        self.current_ai_mode = 'light'
        self.ai_light_colors = {}
        self.ai_dark_colors = {}

        # --- UI Elements ---
        top_bar_ai = ttk.Frame(self)
        top_bar_ai.pack(fill=tk.X, pady=(0, 10))
        ttk.Button(top_bar_ai, text="← Back to Menu", command=lambda: controller.show_frame("MenuFrame")).pack(side=tk.LEFT)

        ai_theme_frame = ttk.Frame(top_bar_ai); ai_theme_frame.pack(side=tk.RIGHT)
        ttk.Label(ai_theme_frame, text="Theme:").pack(side=tk.LEFT, padx=(10,2))
        self.ai_light_button = ttk.Button(ai_theme_frame, text="Light", command=lambda: self.set_mode_ai_from_button('light'))
        self.ai_light_button.pack(side=tk.LEFT, padx=2)
        self.ai_dark_button = ttk.Button(ai_theme_frame, text="Dark", command=lambda: self.set_mode_ai_from_button('dark'))
        self.ai_dark_button.pack(side=tk.LEFT, padx=2)


        control_panel = ttk.Frame(self); control_panel.pack(fill=tk.X, pady=5)
        # Prediction Controls (only if ML libs are available)
        if _ML_LIBS_AVAILABLE:
            ttk.Label(control_panel, text="Predict revenue for next:").pack(side=tk.LEFT, padx=(0, 5))
            self.months_var = tk.StringVar(value="6")
            self.months_spinbox = Spinbox(control_panel, from_=1, to=36, textvariable=self.months_var, width=5, font=('Segoe UI', 10))
            self.months_spinbox.pack(side=tk.LEFT, padx=5)
            ttk.Label(control_panel, text="months").pack(side=tk.LEFT)

            ttk.Label(control_panel, text="  Poly Degree:").pack(side=tk.LEFT, padx=(15, 5))
            self.degree_var = tk.StringVar(value="2")
            self.degree_spinbox = Spinbox(control_panel, from_=1, to=5, textvariable=self.degree_var, width=3, font=('Segoe UI', 10))
            self.degree_spinbox.pack(side=tk.LEFT, padx=5)
            ttk.Button(control_panel, text="Run Prediction 🧠", command=self.run_prediction).pack(side=tk.LEFT, padx=15)
        else:
            ttk.Label(control_panel, text="AI functionality disabled (missing libraries).").pack(side=tk.LEFT, padx=5)


        self.ai_chart_frame_container = ttk.Frame(self, relief=tk.SUNKEN, borderwidth=1)
        self.ai_chart_frame_container.pack(fill=tk.BOTH, expand=True, pady=(10, 0))

        self.status_ai = ttk.Label(self, text="Ready." if _ML_LIBS_AVAILABLE else "AI disabled.", relief=tk.SUNKEN, anchor=tk.W)
        self.status_ai.pack(fill=tk.X, side=tk.BOTTOM, ipady=2)


    def _init_theme_settings(self, mode, light_colors, dark_colors):
        self.ai_light_colors = light_colors
        self.ai_dark_colors = dark_colors
        # Apply initial theme, but canvas creation is deferred
        self.set_mode_ai(mode, light_colors, dark_colors, from_init=True)

    def set_mode_ai_from_button(self, mode):
        # Use the controller to get the authoritative color dicts
        _m, light_colors, dark_colors = self.controller.get_current_theme_settings()
        self.set_mode_ai(mode, light_colors, dark_colors)
        # Optionally sync back to AnalysisFrame
        # if "AnalysisFrame" in self.controller.frames:
        #     self.controller.frames["AnalysisFrame"].set_mode(mode)


    def set_mode_ai(self, mode, light_colors_base, dark_colors_base, from_init=False):
        if mode not in ['light', 'dark']: return
        self.current_ai_mode = mode
        # Use copies for safety
        self.ai_light_colors = light_colors_base.copy()
        self.ai_dark_colors = dark_colors_base.copy()
        colors = self.ai_light_colors if mode == 'light' else self.ai_dark_colors

        # --- Theme AI Frame Widgets ---
        style = self.controller.style # Use main style object
        # Configure specific styles for AI Frame if needed, or reuse Analysis styles
        style.configure('AI.TLabel', background=colors['bg'], foreground=colors['fg'])
        style.configure('AI.TButton', background=colors['button_bg'], foreground=colors['button_fg'])
        # Apply styles to widgets in this frame
        self.configure(style='TFrame') # Main AI frame background
        for widget in self.winfo_children():
             if isinstance(widget, ttk.Frame): widget.configure(style='TFrame')
             # Careful not to override sub-frames like control_panel if they need specific styling
             # Theme specific widgets
             if isinstance(widget, (ttk.Label, ttk.Button)):
                  # Check widget name or add specific styles if needed
                  if hasattr(widget,'cget') and 'text' in widget.config(): # Basic check
                       if 'Theme:' in widget.cget('text'): widget.configure(style='TLabel')
                       # Apply button style carefully
                       # if isinstance(widget, ttk.Button): widget.configure(style='TButton')
        # Status bar needs explicit styling
        self.status_ai.configure(style='Bold.TLabel', background=colors['bg'], foreground=colors['fg'])

        # Theme tk.Spinbox widgets directly
        spin_options = {
            'background': colors.get('spin_bg', colors['widget_bg']), 'foreground': colors.get('spin_fg', colors['fg']),
            'readonlybackground': colors.get('spin_bg', colors['widget_bg']), 'buttonbackground': colors.get('spin_btn_bg', colors['button_bg'])}
        if hasattr(self, 'months_spinbox') and self.months_spinbox: self.months_spinbox.configure(**spin_options)
        if hasattr(self, 'degree_spinbox') and self.degree_spinbox: self.degree_spinbox.configure(**spin_options)

        # --- Theme AI Plot ---
        if self.canvas_ai is not None:
            self._apply_theme_to_ai_plot(mode, self.ai_light_colors, self.ai_dark_colors)
        elif not from_init: # If theme set interactively, ensure canvas exists
             self._ensure_canvas_and_apply_theme(mode, self.ai_light_colors, self.ai_dark_colors)

        # Update theme buttons state
        if hasattr(self, 'ai_light_button'): self.ai_light_button.state(['disabled' if mode == 'light' else '!disabled'])
        if hasattr(self, 'ai_dark_button'): self.ai_dark_button.state(['disabled' if mode == 'dark' else '!disabled'])


    def _ensure_canvas_and_apply_theme(self, mode, light_colors, dark_colors):
        if self.canvas_ai is None and self.ai_chart_frame_container is not None:
            self.fig_ai, self.ax_ai = plt.subplots(figsize=(7, 5))
            self.canvas_ai = FigureCanvasTkAgg(self.fig_ai, master=self.ai_chart_frame_container)
            self.canvas_ai_widget = self.canvas_ai.get_tk_widget()
            self.canvas_ai_widget.pack(fill=tk.BOTH, expand=True)
        self._apply_theme_to_ai_plot(mode, light_colors, dark_colors) # Always apply theme

    def _apply_theme_to_ai_plot(self, mode, light_colors, dark_colors):
        # ... (_apply_theme_to_ai_plot változatlan) ...
        if self.fig_ai is None or self.ax_ai is None or self.canvas_ai is None: return
        colors = light_colors if mode == 'light' else dark_colors
        plot_bg_color = colors.get('plot_bg', colors['widget_bg'])
        self.fig_ai.patch.set_facecolor(colors['bg'])
        self.ax_ai.set_facecolor(plot_bg_color)
        for spine in self.ax_ai.spines.values(): spine.set_color(colors['fg'])
        self.ax_ai.tick_params(axis='x', colors=colors['fg'], labelcolor=colors['fg'])
        self.ax_ai.tick_params(axis='y', colors=colors['fg'], labelcolor=colors['fg'])
        self.ax_ai.title.set_color(colors['fg'])
        if self.ax_ai.get_xlabel(): self.ax_ai.xaxis.label.set_color(colors['fg'])
        if self.ax_ai.get_ylabel(): self.ax_ai.yaxis.label.set_color(colors['fg'])
        legend = self.ax_ai.get_legend()
        if legend:
            legend.get_frame().set_facecolor(colors['bg'])
            legend.get_frame().set_edgecolor(colors['fg'])
            for text in legend.get_texts(): text.set_color(colors['fg'])
        self.canvas_ai.draw_idle()

    def run_prediction(self):
        if not _ML_LIBS_AVAILABLE:
            self.status_ai.config(text="AI functionality disabled (missing libraries).")
            return

        # Ensure theme is applied before plotting
        mode, light_c, dark_c = self.controller.get_current_theme_settings()
        self._ensure_canvas_and_apply_theme(mode, light_c, dark_c) # Ensure canvas exists and has current theme

        try:
            num_months_to_predict = int(self.months_var.get())
            poly_degree = int(self.degree_var.get())
            if not (1 <= num_months_to_predict <= 36): self.status_ai.config(text="Err: Months 1-36."); return
            if not (1 <= poly_degree <= 5): self.status_ai.config(text="Err: Degree 1-5."); return
        except ValueError: self.status_ai.config(text="Err: Invalid number."); return
        except AttributeError: self.status_ai.config(text="Err: AI widgets not initialized."); return # If ML libs failed

        self.status_ai.config(text=f"Processing: Deg-{poly_degree} Poly Forecast ({num_months_to_predict} months)…"); self.update_idletasks()

        try:
            conn = sqlite3.connect(DB_PATH); conn.execute("PRAGMA query_only = ON;")
            df_historical = pd.read_sql_query(QUERIES["Monthly Revenue"], conn); conn.close()

            min_points = poly_degree + 1
            current_mode, lc, dc = self.controller.get_current_theme_settings() # For empty plot text color
            if df_historical.empty or len(df_historical) < min_points:
                self.status_ai.config(text=f"Err: Need >= {min_points} data points for deg {poly_degree}.")
                if self.ax_ai:
                    self.ax_ai.clear(); self.ax_ai.set_aspect('auto') # Clear and reset aspect
                    self.ax_ai.text(0.5, 0.5, "Not enough data.", ha='center', va='center', transform=self.ax_ai.transAxes,
                                    color=lc.get('fg') if current_mode == 'light' else dc.get('fg'))
                    self._apply_theme_to_ai_plot(current_mode, lc, dc)
                return

            df_historical['time_idx'] = np.arange(len(df_historical))
            X_hist, y_hist = df_historical[['time_idx']], df_historical['y']
            model = make_pipeline(PolynomialFeatures(degree=poly_degree, include_bias=False), LinearRegression())
            model.fit(X_hist, y_hist)

            last_idx = df_historical['time_idx'].max()
            future_idxs = np.arange(last_idx + 1, last_idx + 1 + num_months_to_predict)
            X_future = pd.DataFrame(future_idxs, columns=['time_idx']) # Use DataFrame
            y_pred = model.predict(X_future)

            try: # Date labels generation
                last_date_str = df_historical['x'].iloc[-1]; last_date = pd.to_datetime(last_date_str + "-01")
                future_dates = pd.date_range(start=last_date + pd.DateOffset(months=1), periods=num_months_to_predict, freq='MS')
                future_labels = future_dates.strftime('%Y-%m').tolist()
            except Exception as date_err: print(f"Warn: Date parse err - {date_err}"); future_labels = [f"P{i+1}" for i in range(num_months_to_predict)]

            # --- Plotting ---
            self.ax_ai.clear(); self.ax_ai.set_aspect('auto') # Reset aspect ratio here too
            current_mode, current_lc, current_dc = self.controller.get_current_theme_settings()
            colors = current_lc if current_mode == 'light' else current_dc
            hist_c, pred_c, fit_c = colors['accent'], '#FF6347', 'grey'

            y_fit_hist = model.predict(X_hist)
            self.ax_ai.plot(X_hist['time_idx'], y_hist, marker='o', linestyle='-', color=hist_c, label='Historical', markersize=5, linewidth=2)
            self.ax_ai.plot(X_hist['time_idx'], y_fit_hist, linestyle='--', color=fit_c, label=f'Fitted (Deg={poly_degree})', linewidth=1.5)
            self.ax_ai.plot(future_idxs, y_pred, marker='x', linestyle='--', color=pred_c, label=f'Predicted ({num_months_to_predict}mo)', markersize=6, linewidth=2)

            all_indices = list(X_hist['time_idx']) + list(future_idxs)
            all_labels = list(df_historical['x']) + future_labels
            tick_space = max(1, len(all_indices) // 12)
            display_idxs = all_indices[::tick_space]; display_lbls = all_labels[::tick_space]
            self.ax_ai.set_xticks(display_idxs); self.ax_ai.set_xticklabels(display_lbls, rotation=45, ha="right", fontsize=9)

            self.ax_ai.set_title(f'Polynomial Revenue Forecast (Deg={poly_degree}, {num_months_to_predict}mo)', fontsize=14, weight='bold')
            self.ax_ai.set_xlabel('Month (YYYY-MM)'); self.ax_ai.set_ylabel('Revenue')
            self.ax_ai.legend(fontsize=8); self.ax_ai.grid(True, linestyle=':', alpha=0.6)
            self.fig_ai.tight_layout(pad=1.5)
            self._apply_theme_to_ai_plot(current_mode, current_lc, current_dc)
            self.status_ai.config(text="Prediction complete.")

        except sqlite3.Error as e: self.status_ai.config(text=f"DB err: {e}"); print(f"SQL Err pred: {e}")
        except FileNotFoundError: self.status_ai.config(text=f"Err: DB '{DB_PATH}' not found.")
        except Exception as e: self.status_ai.config(text=f"Pred err: {e}"); import traceback; traceback.print_exc()


if __name__ == "__main__":
    # Dependency Checks at start
    missing_libs = []
    try: from PIL import Image, ImageTk
    except ImportError: missing_libs.append("Pillow (pip install Pillow)")
    if not _ML_LIBS_AVAILABLE: # Use the flag set earlier
        missing_libs.append("scikit-learn, numpy (pip install scikit-learn numpy)")
    if missing_libs:
        print("ERROR: Missing required libraries:")
        for lib in missing_libs: print(f"- {lib}")
        sys.exit(1)

    if not os.path.exists(DB_PATH):
        print(f"ERROR: DB file '{DB_PATH}' not found! Run ETL script."); # sys.exit(1)
    app = MainApplication()
    app.mainloop()