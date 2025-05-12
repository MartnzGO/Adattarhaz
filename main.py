# main.py

import sys
import sqlite3
import pandas as pd
import tkinter as tk
from tkinter import ttk, Menu, filedialog
from PIL import Image, ImageTk
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib.pyplot as plt

DB_PATH = "ecommerce_dwh.sqlite"
QUERIES = {
    "Monthly Revenue": """
        SELECT d.year || '-' || printf('%02d', d.month) AS x,
               SUM(f.total_amount) AS y
        FROM Fact_Sales f
        JOIN Dim_Date d ON f.date_key = d.date_key
        GROUP BY d.year, d.month
        ORDER BY d.year, d.month;
    """,
    "Top 10 Categories by Revenue": """
        SELECT p.product_category_name AS x,
               SUM(f.total_amount) AS y
        FROM Fact_Sales f
        JOIN Dim_Product p ON f.product_key = p.product_key
        GROUP BY p.product_category_name
        ORDER BY y DESC
        LIMIT 10;
    """,
    "Orders Count by State": """
        SELECT c.state AS x,
               COUNT(*) AS y
        FROM Fact_Sales f
        JOIN Dim_Customer c ON f.customer_key = c.customer_key
        GROUP BY c.state
        ORDER BY y DESC;
    """,
    "Payment Type Distribution": """
        SELECT p.payment_type AS x,
               SUM(f.total_amount) AS y
        FROM Fact_Sales f
        JOIN Dim_Payment p ON f.payment_key = p.payment_key
        GROUP BY p.payment_type;
    """
}


class MainApplication(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("📊 E-Commerce DWH Dashboard")
        self.geometry("900x650")
        # ensure proper exit on window close
        self.protocol("WM_DELETE_WINDOW", self.on_close)

        # Grid-layout full window
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        container = ttk.Frame(self)
        container.grid(row=0, column=0, sticky="nsew")
        container.columnconfigure(0, weight=1)
        container.rowconfigure(0, weight=1)

        self.frames = {}
        for F in (MenuFrame, AnalysisFrame, AIFrame):
            frame = F(parent=container, controller=self)
            self.frames[F.__name__] = frame
            frame.grid(row=0, column=0, sticky="nsew")

        self.show_frame("MenuFrame")

    def on_close(self):
        self.destroy()
        sys.exit(0)

    def show_frame(self, name):
        self.frames[name].tkraise()


class MenuFrame(ttk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller

        # Two-column grid
        self.columnconfigure(0, weight=1)
        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=0)
        self.rowconfigure(1, weight=1)

        title = ttk.Label(self, text="Welcome to E-Commerce Dashboard",
                          font=("Segoe UI", 20, "bold"))
        title.grid(row=0, column=0, columnspan=2, pady=(40,20))

        # load images
        self.normal_orig = Image.open("Normal.jpg")
        self.ai_orig     = Image.open("AI.jpg")

        self.normal_btn = ttk.Button(
            self, text="Normal Analysis", compound="top",
            command=lambda: controller.show_frame("AnalysisFrame")
        )
        self.normal_btn.grid(row=1, column=0, sticky="nsew", padx=20, pady=10)
        self.normal_btn.bind("<Configure>", self._resize_normal)

        self.ai_btn = ttk.Button(
            self, text="AI Interface", compound="top",
            command=lambda: controller.show_frame("AIFrame")
        )
        self.ai_btn.grid(row=1, column=1, sticky="nsew", padx=20, pady=10)
        self.ai_btn.bind("<Configure>", self._resize_ai)

    def _resize_normal(self, event):
        w, h = event.width, event.height
        img_h = max(h - 32, 10)
        img = self.normal_orig.resize((w, img_h), Image.LANCZOS)
        self.normal_photo = ImageTk.PhotoImage(img)
        self.normal_btn.config(image=self.normal_photo)

    def _resize_ai(self, event):
        w, h = event.width, event.height
        img_h = max(h - 32, 10)
        img = self.ai_orig.resize((w, img_h), Image.LANCZOS)
        self.ai_photo = ImageTk.PhotoImage(img)
        self.ai_btn.config(image=self.ai_photo)


class AnalysisFrame(ttk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent, padding=10)
        self.controller = controller

        ttk.Button(self, text="← Back",
                   command=lambda: controller.show_frame("MenuFrame")).pack(anchor="w")

        theme_frame = ttk.Frame(self)
        theme_frame.pack(fill=tk.X, pady=5)
        ttk.Label(theme_frame, text="Theme:").pack(side=tk.LEFT)
        ttk.Button(theme_frame, text="Light",
                   command=lambda: self.set_mode('light')).pack(side=tk.LEFT, padx=2)
        ttk.Button(theme_frame, text="Dark",
                   command=lambda: self.set_mode('dark')).pack(side=tk.LEFT, padx=2)

        controls = ttk.Frame(self)
        controls.pack(fill=tk.X, pady=5)
        ttk.Label(controls, text="Select Report:").pack(side=tk.LEFT)
        self.combo = ttk.Combobox(controls, values=list(QUERIES.keys()),
                                  state="readonly", width=30)
        self.combo.current(0)
        self.combo.pack(side=tk.LEFT, padx=5)
        ttk.Button(controls, text="Run ▶", command=self.run_query).pack(side=tk.LEFT, padx=5)
        ttk.Button(controls, text="Save ▶", command=self.save_plot).pack(side=tk.LEFT, padx=5)

        chart_frame = ttk.Frame(self, relief=tk.SUNKEN)
        chart_frame.pack(fill=tk.BOTH, expand=True, pady=10)
        self.fig, self.ax = plt.subplots(figsize=(6,4))
        self.canvas = FigureCanvasTkAgg(self.fig, master=chart_frame)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        self.status = ttk.Label(self, text="Ready", relief=tk.SUNKEN, anchor=tk.W)
        self.status.pack(fill=tk.X, side=tk.BOTTOM)

        self._create_styles()

    def _create_styles(self):
        self.style = ttk.Style(self)
        self.light_colors = {'bg':'#f0f0f0','fg':'#000000',
                             'button_bg':'#e0e0e0','button_fg':'#000000'}
        self.dark_colors  = {'bg':'#2e2e2e','fg':'#ffffff',
                             'button_bg':'#444444','button_fg':'#ffffff'}
        for w in ('TFrame','TLabel','TCombobox'):
            self.style.configure(w, font=('Segoe UI',10))
        self.style.configure('TButton', font=('Segoe UI',12,'bold'))
        self.set_mode('light')

    def set_mode(self, mode):
        self.current_mode = mode
        colors = self.light_colors if mode=='light' else self.dark_colors
        self.configure(style='TFrame')
        self.style.configure('TFrame',    background=colors['bg'])
        self.style.configure('TLabel',    background=colors['bg'], foreground=colors['fg'])
        self.style.configure('TButton',   background=colors['button_bg'], foreground=colors['button_fg'])
        self.style.configure('TCombobox', fieldbackground=colors['bg'], foreground=colors['fg'])
        self.fig.patch.set_facecolor(colors['bg'])
        self.ax.set_facecolor(colors['bg'])
        for spine in self.ax.spines.values(): spine.set_color(colors['fg'])
        self.ax.tick_params(colors=colors['fg'], labelcolor=colors['fg'])
        self.ax.title.set_color(colors['fg'])
        self.canvas.draw()

    def run_query(self):
        name = self.combo.get()
        self.status.config(text=f"Running: {name}…")
        conn = sqlite3.connect(DB_PATH)
        df = pd.read_sql_query(QUERIES[name], conn)
        conn.close()

        self.fig.clf()
        self.ax = self.fig.add_subplot(111)
        x, y = df['x'], df['y']
        cmap = plt.get_cmap('tab10').colors

        if "Distribution" in name:
            textcol = (self.light_colors if self.current_mode=='light' else self.dark_colors)['fg']
            self.ax.pie(y, labels=x, autopct='%1.1f%%', textprops={'color': textcol})
        elif "Categories" in name or "State" in name:
            self.ax.bar(x, y, color=cmap[:len(x)])
            self.ax.set_xticks(range(len(x)))
            self.ax.set_xticklabels(x, rotation=45, ha='right', fontsize=9)
        else:
            linecol = (self.light_colors if self.current_mode=='light' else self.dark_colors)['button_fg']
            self.ax.plot(x, y, marker='o', color=linecol)
            self.ax.set_xticks(range(len(x)))
            self.ax.set_xticklabels(x, rotation=45, ha='right', fontsize=9)

        fg = (self.light_colors if self.current_mode=='light' else self.dark_colors)['fg']
        bg = (self.light_colors if self.current_mode=='light' else self.dark_colors)['bg']
        self.ax.set_title(name, color=fg)
        self.ax.set_ylabel("Value", color=fg)
        self.ax.set_facecolor(bg)

        self.fig.tight_layout()
        self.canvas.draw()
        self.status.config(text=f"Done: {name}")

    def save_plot(self):
        fname = filedialog.asksaveasfilename(defaultextension=".png",
                                             filetypes=[("PNG Image","*.png"),("All files","*.*")],
                                             title="Save Plot As...")
        if fname:
            self.fig.savefig(fname, facecolor=self.fig.get_facecolor(), dpi=150)
            self.status.config(text=f"Saved plot to {fname}")


class AIFrame(ttk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent, padding=20)
        ttk.Label(self, text="🤖 AI Interface (coming soon)",
                  font=("Segoe UI",16)).pack(pady=40)
        ttk.Button(self, text="← Back",
                   command=lambda: controller.show_frame("MenuFrame")).pack()


if __name__ == "__main__":
    app = MainApplication()
    app.mainloop()
