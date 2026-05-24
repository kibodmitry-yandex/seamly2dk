import tkinter as tk
from tkinter import filedialog, messagebox
import threading
from svg_parser import parse_svg
from opd import build_opd
from sidecar import Sidecar
from app_state import load_state, save_state
import os


class App:
    def __init__(self, root):
        self.root = root
        root.title('seamly2dk — OPD exporter (MVP)')

        # Header: open button + dropdown
        header = tk.Frame(root)
        header.grid(row=0, column=0, columnspan=2, sticky='ew', padx=4, pady=4)
        self.open_btn = tk.Button(header, text='Open SVG', command=self.open_file)
        self.open_btn.pack(side='left')

        self.piece_var = tk.StringVar()
        self.piece_menu = tk.OptionMenu(header, self.piece_var, '')
        self.piece_menu.pack(side='left', padx=8)
        # Clear selection button
        self.clear_sel_btn = tk.Button(header, text='Clear selection', command=self.on_clear_selection)
        self.clear_sel_btn.pack(side=tk.LEFT, padx=4)
        # show vertices toggle
        self.show_vertices = tk.BooleanVar(value=False)
        self.show_vertices_cb = tk.Checkbutton(header, text='Show vertices', variable=self.show_vertices, command=self.on_show_vertices_toggle)
        self.show_vertices_cb.pack(side='left', padx=8)
        # register trace and keep id so we can temporarily disable it when setting value programmatically
        self.piece_var_trace_id = self.piece_var.trace_add('write', lambda *a: self.on_piece_var_change())

        # Canvas spans full width
        self.canvas = tk.Canvas(root, bg='white')
        self.canvas.grid(row=1, column=0, columnspan=2, sticky='nsew')
        # bind zoom/pan events: mouse wheel for zoom, middle/right drag for pan
        self.canvas.bind('<MouseWheel>', lambda e: self.on_mouse_wheel(e))
        self.canvas.bind('<ButtonPress-2>', lambda e: self.on_pan_start(e))
        self.canvas.bind('<B2-Motion>', lambda e: self.on_pan_move(e))
        self.canvas.bind('<ButtonRelease-2>', lambda e: self.on_pan_end(e))
        # also bind right-button as pan alternative
        self.canvas.bind('<ButtonPress-3>', lambda e: self.on_pan_start(e))
        self.canvas.bind('<B3-Motion>', lambda e: self.on_pan_move(e))
        self.canvas.bind('<ButtonRelease-3>', lambda e: self.on_pan_end(e))
        # Note: Shift+Left will be used for multi-select of points (not pan)

        # initialize runtime attributes
        self.current_file = None
        self.pieces = []
        self.sidecar = None
        self.last_canvas_transform = None
        self._pan_state = None
        self._current_piece_idx = None
        # selected items: canvas ids and persistent descriptors
        self._selected_items = []
        self._selected_descs = []

        # load app state early
        self.app_state = load_state()
        geom = self.app_state.get('window_geometry')
        if geom:
            try:
                root.geometry(geom)
            except Exception:
                pass

        # Bottom split: use PanedWindow so sash can be dragged to resize panes
        paned = tk.PanedWindow(root, orient='horizontal')
        paned.grid(row=2, column=0, columnspan=2, sticky='nsew', padx=4, pady=4)

        bottom_left = tk.Frame(paned)
        bottom_right = tk.Frame(paned)
        paned.add(bottom_left, minsize=120)
        paned.add(bottom_right, minsize=120)

        self.coords_text = tk.Text(bottom_left, width=60, height=10)
        self.coords_text.pack(fill='both', expand=True)

        # OPD field slightly shorter vertically so the Copy button fits under it
        self.opd_text = tk.Text(bottom_right, width=40, height=7)
        self.opd_text.pack(fill='both', expand=True)
        self.copy_btn = tk.Button(bottom_right, text='Copy OPD', command=self.copy_opd)
        self.copy_btn.pack(fill='x', pady=(4,0))

        root.grid_columnconfigure(0, weight=1)
        root.grid_columnconfigure(1, weight=1)
        root.grid_rowconfigure(1, weight=1)
        root.grid_rowconfigure(2, weight=0)

        # set initial sash position after window appears
        def set_sash():
            try:
                w = root.winfo_width()
                # if saved sash position present, use it, else put at 65% of width
                sash_x = self.app_state.get('sash_x')
                if sash_x is not None:
                    paned.sash_place(0, int(sash_x), 0)
                else:
                    paned.sash_place(0, int(w * 0.65), 0)
            except Exception:
                pass

        self.paned = paned
        root.after(100, set_sash)
        # start autosave loop
        root.after(2000, self.autosave)
        # restore last opened file if present
        last_file = self.app_state.get('last_file')
        if last_file and os.path.exists(last_file):
            root.after(300, lambda: self.open_file(last_file))

        root.protocol('WM_DELETE_WINDOW', self.on_close)

    def on_close(self):
        # perform one final save
        try:
            self.autosave()
        except Exception:
            pass
        try:
            self.root.destroy()
        except Exception:
            pass

    def open_file(self, path=None):
        if path is None:
            path = filedialog.askopenfilename(filetypes=[('SVG files','*.svg'), ('All','*.*')])
        if not path:
            return
        try:
            self.pieces = parse_svg(path)
            self.current_file = path
            self.sidecar = Sidecar(path)
            # restore per-file state from sidecar
            self.populate_pieces()
            # set last selected piece from sidecar if present
            last_sel = self.sidecar.data.get('last_selected')
            if last_sel:
                # find matching name
                for i,p in enumerate(self.pieces):
                    if (p.get('name') or f'piece_{i}') == last_sel:
                        self.piece_var.set(last_sel)
                        break
            # draw the piece that is currently selected in the menu (restores last_selected)
            sel_name = self.piece_var.get() if hasattr(self, 'piece_var') else None
            sel_idx = 0
            if sel_name:
                for i,p in enumerate(self.pieces):
                    if (p.get('name') or f'piece_{i}') == sel_name:
                        sel_idx = i
                        break
            # draw selected piece
            self.draw_piece(sel_idx)
            # update app state last file
            self.app_state['last_file'] = path
            save_state(self.app_state)
        except Exception as e:
            messagebox.showerror('Error', str(e))

    def populate_pieces(self):
        menu = self.piece_menu['menu']
        menu.delete(0, 'end')
        names = []
        for i,p in enumerate(self.pieces):
            name = p.get('name') or f'piece_{i}'
            names.append(name)
            menu.add_command(label=name, command=lambda v=name: self.piece_var.set(v))
        if names:
            # set to first without triggering trace callback (prevents overwriting sidecar)
            try:
                if hasattr(self, 'piece_var_trace_id'):
                    self.piece_var.trace_remove('write', self.piece_var_trace_id)
            except Exception:
                pass
            try:
                self.piece_var.set(names[0])
            finally:
                # re-register trace
                try:
                    self.piece_var_trace_id = self.piece_var.trace_add('write', lambda *a: self.on_piece_var_change())
                except Exception:
                    pass
        # ensure clear selection button state
        try:
            self.clear_sel_btn.config(state='normal')
        except Exception:
            pass

    def on_piece_var_change(self):
        name = self.piece_var.get()
        for i,p in enumerate(self.pieces):
            if (p.get('name') or f'piece_{i}') == name:
                self.draw_piece(i)
                break

    def on_show_vertices_toggle(self):
        # redraw current piece and persist show_vertices in sidecar
        try:
            name = self.piece_var.get()
            idx = 0
            for i,p in enumerate(self.pieces):
                if (p.get('name') or f'piece_{i}') == name:
                    idx = i; break
        except Exception:
            idx = 0
        # persist per-file
        try:
            if self.sidecar:
                key = (self.piece_var.get() or f'piece_{idx}')
                pieces_state = self.sidecar.data.get('pieces', {})
                pieces_state[key] = pieces_state.get(key, {})
                pieces_state[key]['show_vertices'] = bool(self.show_vertices.get())
                self.sidecar.data['pieces'] = pieces_state
                self.sidecar.save()
        except Exception:
            pass
        self.draw_piece(idx)

    def on_clear_selection(self):
        # clear visual selection and descriptors, persist
        try:
            for it in list(self._selected_items):
                try:
                    self.canvas.itemconfig(it, fill='gray', outline='black')
                except Exception:
                    pass
            self._selected_items = []
            self._selected_descs = []
            # clear persisted selection for current piece
            if self.sidecar:
                key = (self.piece_var.get() or f'piece_{self._current_piece_idx}')
                pieces = self.sidecar.data.setdefault('pieces', {})
                st = pieces.setdefault(key, {})
                st.pop('selection', None)
                self.sidecar.save()
            # clear coords_text
            try:
                self.coords_text.delete('1.0', tk.END)
            except Exception:
                pass
        except Exception:
            pass

    def draw_piece(self, idx):
        self.canvas.delete('all')
        if idx >= len(self.pieces):
            return
        piece = self.pieces[idx]
        paths = piece.get('paths', [])
        # compute bbox
        xs = []
        ys = []
        for path in paths:
            for x,y in path['points']:
                xs.append(x); ys.append(y)
        if not xs:
            return
        minx, maxx = min(xs), max(xs)
        miny, maxy = min(ys), max(ys)
        w = maxx - minx if maxx>minx else 1
        h = maxy - miny if maxy>miny else 1
        try:
            canv_w = int(self.canvas.winfo_width()) or int(self.canvas['width'])
            canv_h = int(self.canvas.winfo_height()) or int(self.canvas['height'])
        except Exception:
            canv_w = int(self.canvas['width']); canv_h = int(self.canvas['height'])
        default_scale = min((canv_w-20)/w, (canv_h-20)/h)

        # check for saved per-piece canvas transform in sidecar
        saved_transform = None
        try:
            if self.sidecar:
                key = (self.piece_var.get() or f'piece_{idx}')
                saved_transform = self.sidecar.data.get('pieces', {}).get(key, {}).get('canvas')
                # restore show_vertices preference early so drawing uses it
                sv = self.sidecar.data.get('pieces', {}).get(key, {}).get('show_vertices')
                if sv is not None:
                    try:
                        self.show_vertices.set(bool(sv))
                    except Exception:
                        pass
        except Exception:
            saved_transform = None

        if saved_transform and isinstance(saved_transform, dict) and 'scale' in saved_transform and 'minx' in saved_transform and 'miny' in saved_transform:
            scale = saved_transform.get('scale', default_scale)
            minx = saved_transform.get('minx', minx)
            miny = saved_transform.get('miny', miny)
        else:
            scale = default_scale

        def to_canvas(pt):
            x,y = pt
            cx = (x - minx) * scale + 10
            cy = (y - miny) * scale + 10
            return (cx, cy)

        # clear mapping
        self._canvas_map = {}
        # clear selected control point
        self._selected_ctrl = None
        # do not clear selection on redraw unless piece changed
        if self._current_piece_idx is None or self._current_piece_idx != idx:
            # switching to a new piece: clear in-memory selection descriptors
            self._selected_items = []
            self._selected_descs = []
        # after drawing, restore per-piece saved selection if exists
        restore_sel = False
        for pi, path in enumerate(paths):
            pts = [to_canvas(p) for p in path['points']]
            flat = []
            for (x,y) in pts:
                flat.extend((x,y))
            color = 'red' if path.get('is_curve') else 'black'
            if len(flat) >= 4:
                item = self.canvas.create_line(*flat, fill=color, width=1.5)
                # tag item
                tag = f'piece{idx}_path{pi}'
                self.canvas.addtag_withtag(tag, item)
                if path.get('is_curve'):
                    self.canvas.addtag_withtag('curve', item)
                # store mapping for callbacks
                self._canvas_map[item] = (idx, pi)
                # bind click
                self.canvas.tag_bind(tag, '<Button-1>', self.on_canvas_click)
                # if this path contains cubic segments, draw control points
                try:
                    for si, s in enumerate(path.get('segs', [])):
                        if s[0] == 'C':
                            # s = ('C', p0,p1,p2,p3)
                            p1 = s[2]
                            p2 = s[3]
                            # convert to canvas coords
                            c1 = to_canvas(p1)
                            c2 = to_canvas(p2)
                            r = 4
                            o1 = self.canvas.create_oval(c1[0]-r, c1[1]-r, c1[0]+r, c1[1]+r, fill='blue', outline='black')
                            o2 = self.canvas.create_oval(c2[0]-r, c2[1]-r, c2[0]+r, c2[1]+r, fill='blue', outline='black')
                            tag1 = f'ctrl_{idx}_{pi}_{si}_p1'
                            tag2 = f'ctrl_{idx}_{pi}_{si}_p2'
                            self.canvas.addtag_withtag(tag1, o1)
                            self.canvas.addtag_withtag(tag2, o2)
                            # map items to ctrl info
                            self._canvas_map[o1] = ('ctrl', idx, pi, si, 'p1')
                            self._canvas_map[o2] = ('ctrl', idx, pi, si, 'p2')
                            # bind ctrl click
                            self.canvas.tag_bind(tag1, '<Button-1>', self.on_ctrl_click)
                            self.canvas.tag_bind(tag2, '<Button-1>', self.on_ctrl_click)
                except Exception:
                    pass
                # optionally draw all vertices as small gray dots when toggled
                try:
                    if self.show_vertices.get():
                        for vi, wp in enumerate(path['points']):
                            cx, cy = to_canvas(wp)
                            r = 3
                            oval = self.canvas.create_oval(cx-r, cy-r, cx+r, cy+r, fill='gray', outline='black')
                            tagv = f'vert_{idx}_{pi}_{vi}'
                            self.canvas.addtag_withtag(tagv, oval)
                            self._canvas_map[oval] = ('vert', idx, pi, vi)
                            self.canvas.tag_bind(tagv, '<Button-1>', self.on_ctrl_click)
                except Exception:
                    pass
        # record canvas transform in mm for potential restore
        self.last_canvas_transform = {'minx': minx, 'miny': miny, 'scale': scale, 'canv_w': canv_w, 'canv_h': canv_h}

        # restore saved selection for this piece if present
        try:
            if self.sidecar:
                key = (self.piece_var.get() or f'piece_{idx}')
                piece_state = self.sidecar.data.get('pieces', {}).get(key, {})
                if piece_state:
                    sel = piece_state.get('selection')
                    if sel:
                        # load persistent descriptors into in-memory descriptors
                        try:
                            self._selected_descs = list(sel)
                        except Exception:
                            self._selected_descs = []
                        # map descriptors to current canvas item ids
                        new_selected = []
                        for sdesc in self._selected_descs:
                            for cid, info in list(self._canvas_map.items()):
                                if not isinstance(info, tuple):
                                    continue
                                if sdesc.get('kind') == 'vert' and info[0] == 'vert':
                                    # descriptor contains path_idx and vi
                                    if info[2] == sdesc.get('path_idx') and info[3] == sdesc.get('vi') and info[1] == idx:
                                        new_selected.append(cid); break
                                if sdesc.get('kind') == 'ctrl' and info[0] == 'ctrl':
                                    if info[2] == sdesc.get('path_idx') and info[3] == sdesc.get('seg_idx') and info[4] == sdesc.get('which') and info[1] == idx:
                                        new_selected.append(cid); break
                        if new_selected:
                            self._selected_items = new_selected
                            for it in self._selected_items:
                                try:
                                    self.canvas.itemconfig(it, fill='orange', outline='yellow')
                                except Exception:
                                    pass
                            try:
                                self._compute_and_display_selection()
                            except Exception:
                                pass
        except Exception:
            pass
        # remember current piece index
        self._current_piece_idx = idx

        # show coords of first path in coords_text and OPD in opd_text
        if paths:
            coords_lines = []
            for x,y in paths[0]['points']:
                coords_lines.append(f'{x:.3f}\t{y:.3f}')
            # do not overwrite coords_text if there is an active selection
            if not self._selected_items:
                self.coords_text.delete('1.0', tk.END)
                self.coords_text.insert(tk.END, '\n'.join(coords_lines))

            opd = build_opd(paths[0]['points'], origin='center')
            self.opd_text.delete('1.0', tk.END)
            self.opd_text.insert(tk.END, opd)

            # update sidecar with canvas/piece state
            try:
                if self.sidecar:
                    key = (self.piece_var.get() or f'piece_0')
                    pieces_state = self.sidecar.data.get('pieces', {})
                    pieces_state[key] = pieces_state.get(key, {})
                    pieces_state[key]['canvas'] = self.last_canvas_transform
                    self.sidecar.data['pieces'] = pieces_state
                    self.sidecar.data['last_selected'] = key
                    # save sidecar immediately so selection persists across restarts
                    try:
                        self.sidecar.save()
                    except Exception:
                        pass
            except Exception:
                pass

    # --- curve helpers ---
    def cubic_point(self, p0, p1, p2, p3, t):
        x = ((1-t)**3)*p0[0] + 3*((1-t)**2)*t*p1[0] + 3*(1-t)*(t**2)*p2[0] + (t**3)*p3[0]
        y = ((1-t)**3)*p0[1] + 3*((1-t)**2)*t*p1[1] + 3*(1-t)*(t**2)*p2[1] + (t**3)*p3[1]
        return (x,y)

    def cubic_length(self, p0,p1,p2,p3, steps=20):
        prev = p0
        total = 0.0
        for i in range(1, steps+1):
            t = i/steps
            pt = self.cubic_point(p0,p1,p2,p3,t)
            dx = pt[0]-prev[0]; dy = pt[1]-prev[1]
            total += (dx*dx+dy*dy)**0.5
            prev = pt
        return total

    def convert_path_curves(self, piece_idx, path_idx, segments_per_curve):
        piece = self.pieces[piece_idx]
        path = piece['paths'][path_idx]
        new_points = []
        new_segs = []
        for s in path.get('segs', []):
            if s[0] == 'L':
                a,b = s[1], s[2]
                if not new_points:
                    new_points.append(a)
                new_points.append(b)
                new_segs.append(('L', a, b))
            elif s[0] == 'C':
                p0,p1,p2,p3 = s[1],s[2],s[3],s[4]
                n = max(1, int(segments_per_curve))
                # generate n segments -> n+1 points
                for i in range(0, n+1):
                    t = i / n
                    pt = self.cubic_point(p0,p1,p2,p3,t)
                    if not new_points:
                        new_points.append(pt)
                    else:
                        # avoid duplicate equal to last
                        last = new_points[-1]
                        if abs(pt[0]-last[0])>1e-9 or abs(pt[1]-last[1])>1e-9:
                            new_points.append(pt)
                # add corresponding L segments
                for i in range(len(new_points)- (n), len(new_points)):
                    # link from new_points[i] to new_points[i+1]
                    pass
                # append L segs for the newly added section
                # rebuild L segments from the last (n+1) points
                start_i = len(new_points) - (n+1)
                for j in range(start_i, start_i + n):
                    a = new_points[j]
                    b = new_points[j+1]
                    new_segs.append(('L', a, b))
            else:
                # unknown: skip
                pass
        # replace path data
        path['points'] = new_points
        path['segs'] = new_segs
        path['is_curve'] = False
        # persist change in sidecar
        try:
            if self.sidecar:
                key = (self.piece_var.get() or f'piece_0')
                pieces_state = self.sidecar.data.get('pieces', {})
                pieces_state[key] = pieces_state.get(key, {})
                pieces_state[key].setdefault('converted_paths', {})
                pieces_state[key]['converted_paths'][f'path_{path_idx}'] = new_points
                self.sidecar.data['pieces'] = pieces_state
                self.sidecar.save()
        except Exception:
            pass

    def on_canvas_click(self, event):
        # find the item clicked
        # prefer the canvas 'current' item (the one under the cursor), fallback to nearest
        items = self.canvas.find_withtag('current')
        if items:
            item = items[-1]
        else:
            x = event.x; y = event.y
            item = self.canvas.find_closest(x,y)
            if not item:
                return
            item = item[0]
        # check mapping
        mp = getattr(self, '_canvas_map', {})
        if item not in mp:
            return
        info = mp[item]
        # if this maps to a ctrl point or vertex, forward to ctrl handler
        if isinstance(info, tuple) and info[0] in ('ctrl', 'vert'):
            return self.on_ctrl_click(event)
        piece_idx, path_idx = info
        path = self.pieces[piece_idx]['paths'][path_idx]
        if not path.get('is_curve'):
            return
        # suggest segments based on total curve length (sum of cubic lengths)
        total_len = 0.0
        for s in path.get('segs', []):
            if s[0] == 'C':
                total_len += self.cubic_length(s[1],s[2],s[3],s[4], steps=30)
        # suggest segments so that segment length ~>=5 mm
        suggested = max(3, int((total_len / 5.0) + 0.5))
        # ask user
        try:
            import tkinter.simpledialog as sd
            n = sd.askinteger('Convert curve', f'Number of segments (suggested {suggested})', initialvalue=suggested, minvalue=1)
            if n is None:
                return
            # perform conversion
            self.convert_path_curves(piece_idx, path_idx, n)
            # redraw piece
            # ensure menu selection corresponds
            if self.piece_var.get() != (self.pieces[piece_idx].get('name') or f'piece_{piece_idx}'):
                # temporarily disable trace
                try:
                    self.piece_var.trace_remove('write', self.piece_var_trace_id)
                except Exception:
                    pass
                self.piece_var.set(self.pieces[piece_idx].get('name') or f'piece_{piece_idx}')
                try:
                    self.piece_var_trace_id = self.piece_var.trace_add('write', lambda *a: self.on_piece_var_change())
                except Exception:
                    pass
            self.draw_piece(piece_idx)
        except Exception as e:
            messagebox.showerror('Error', str(e))

    def copy_opd(self):
        txt = self.opd_text.get('1.0', tk.END).strip()
        if not txt:
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(txt)
        messagebox.showinfo('Copied', 'OPD copied to clipboard')

    def on_ctrl_click(self, event):
        # handle click on a control point oval
        x = event.x; y = event.y
        item = self.canvas.find_closest(x,y)
        if not item:
            return
        item = item[0]
        mp = getattr(self, '_canvas_map', {})
        info = mp.get(item)
        if not info or not isinstance(info, tuple):
            return
        kind = info[0]
        if kind == 'ctrl':
            _, piece_idx, path_idx, seg_idx, which = info
            seg = self.pieces[piece_idx]['paths'][path_idx]['segs'][seg_idx]
            # seg = ('C', p0,p1,p2,p3) -> select p1 or p2
            if seg[0] != 'C':
                return
            if which == 'p1':
                pt = seg[2]
            else:
                pt = seg[3]
            # map ctrl to nearest vertex index on the path for length calculations
            nearest_vi = None
            try:
                pts = self.pieces[piece_idx]['paths'][path_idx]['points']
                min_d = 1e12
                for vi, wp in enumerate(pts):
                    dx = wp[0]-pt[0]; dy = wp[1]-pt[1]
                    d = (dx*dx+dy*dy)**0.5
                    if d < min_d:
                        min_d = d; nearest_vi = vi
            except Exception:
                nearest_vi = None
        elif kind == 'vert':
            _, piece_idx, path_idx, vi = info
            pt = self.pieces[piece_idx]['paths'][path_idx]['points'][vi]
            nearest_vi = vi
        else:
            return

        # Selection handling: Shift for multi-select toggle
        # event.state bitmask can vary; check common Shift masks
        st = getattr(event, 'state', 0)
        # consider multiple modifier bits: Shift(0x0001), Control(0x0004), Alt(0x0008)
        shift = (st & 0x0001) != 0 or (st & 0x0004) != 0 or (st & 0x0008) != 0
        if shift:
            # toggle selection of this item
            if item in self._selected_items:
                # deselect
                try:
                    self.canvas.itemconfig(item, fill='gray', outline='black')
                except Exception:
                    pass
                # remove from selected_items and descriptors
                self._selected_items.remove(item)
                # remove corresponding desc
                info = mp.get(item)
                if info and info[0] == 'vert':
                    self._selected_descs = [d for d in self._selected_descs if not (d.get('kind')=='vert' and d.get('path_idx')==info[2] and d.get('vi')==info[3])]
                elif info and info[0] == 'ctrl':
                    self._selected_descs = [d for d in self._selected_descs if not (d.get('kind')=='ctrl' and d.get('path_idx')==info[2] and d.get('seg_idx')==info[3] and d.get('which')==info[4])]
            else:
                try:
                    self.canvas.itemconfig(item, fill='orange', outline='yellow')
                except Exception:
                    pass
                self._selected_items.append(item)
                # add descriptor
                info = mp.get(item)
                if info and info[0] == 'vert':
                    self._selected_descs.append({'kind':'vert','path_idx':info[2],'vi':info[3]})
                elif info and info[0] == 'ctrl':
                    self._selected_descs.append({'kind':'ctrl','path_idx':info[2],'seg_idx':info[3],'which':info[4]})
        else:
            # clear previous selection
            # clear previous selection descriptors and items
            for it in list(self._selected_items):
                try:
                    self.canvas.itemconfig(it, fill='gray', outline='black')
                except Exception:
                    pass
            self._selected_items = [item]
            self._selected_descs = []
            info = mp.get(item)
            if info and info[0] == 'vert':
                self._selected_descs.append({'kind':'vert','path_idx':info[2],'vi':info[3]})
            elif info and info[0] == 'ctrl':
                self._selected_descs.append({'kind':'ctrl','path_idx':info[2],'seg_idx':info[3],'which':info[4]})
            try:
                self.canvas.itemconfig(item, fill='orange', outline='yellow')
            except Exception:
                pass

        # update coords_text and lengths between consecutive selected points
        try:
            out_lines = []
            # build list of (piece_idx, path_idx, vi, coord)
            sel_infos = []
            for it in self._selected_items:
                inf = self._canvas_map.get(it)
                if not inf: continue
                if inf[0] == 'vert':
                    _, pi, pth, vi = inf
                    coord = self.pieces[pi]['paths'][pth]['points'][vi]
                    sel_infos.append((pi, pth, vi, coord))
                elif inf[0] == 'ctrl':
                    _, pi, pth, seg_idx, which = inf
                    seg = self.pieces[pi]['paths'][pth]['segs'][seg_idx]
                    if which == 'p1': coord = seg[2]
                    else: coord = seg[3]
                    # find nearest vi as above
                    pts = self.pieces[pi]['paths'][pth]['points']
                    min_d = 1e12; nvi = 0
                    for vi2, wp in enumerate(pts):
                        dx = wp[0]-coord[0]; dy = wp[1]-coord[1]
                        d = (dx*dx+dy*dy)**0.5
                        if d < min_d:
                            min_d = d; nvi = vi2
                    sel_infos.append((pi, pth, nvi, coord))
            # interleave coords and lengths: coord \n length \n coord \n ...
            for i in range(len(sel_infos)):
                coord = sel_infos[i][3]
                out_lines.append(f'{coord[0]:.3f}\t{coord[1]:.3f}')
                if i < len(sel_infos)-1:
                    a = sel_infos[i]; b = sel_infos[i+1]
                    if a[0]==b[0] and a[1]==b[1]:
                        pts = self.pieces[a[0]]['paths'][a[1]]['points']
                        la = a[2]; lb = b[2]
                        length = 0.0
                        if la != lb:
                            n = len(pts)
                            j = la
                            while j != lb:
                                kidx = (j+1) % n
                                dx = pts[kidx][0]-pts[j][0]; dy = pts[kidx][1]-pts[j][1]
                                length += (dx*dx+dy*dy)**0.5
                                j = kidx
                        out_lines.append(f'{length:.3f} mm')
                    else:
                        out_lines.append('N/A (different paths)')
            # DEBUG: show selected infos and output lines
            self.coords_text.delete('1.0', 'end')
            text_block = '\n'.join(out_lines)
            self.coords_text.insert('1.0', text_block)
        except Exception:
            pass
        # update coords_text and lengths between consecutive selected points
        try:
            self._compute_and_display_selection()
        except Exception:
            pass
        # persist selection into sidecar for current piece
        try:
            if self.sidecar:
                key = (self.piece_var.get() or f'piece_0')
                pieces_state = self.sidecar.data.get('pieces', {})
                pieces_state[key] = pieces_state.get(key, {})
                # store show_vertices as well
                pieces_state[key]['show_vertices'] = bool(self.show_vertices.get())
                # serialize selection descriptors
                pieces_state[key]['selection'] = list(self._selected_descs)
                self.sidecar.data['pieces'] = pieces_state
                self.sidecar.save()
        except Exception:
            pass
        # stop event propagation so line handler does not overwrite selection
        return 'break'

    # --- coordinate transforms and interactions ---
    def screen_to_world(self, cx, cy):
        # convert canvas coords to world (mm) using last_canvas_transform
        t = self.last_canvas_transform or {}
        scale = t.get('scale', 1.0)
        minx = t.get('minx', 0.0)
        miny = t.get('miny', 0.0)
        wx = (cx - 10) / scale + minx
        wy = (cy - 10) / scale + miny
        return (wx, wy)

    def update_transform_and_redraw(self, idx):
        # persist last_canvas_transform into sidecar and redraw
        try:
            if self.sidecar:
                key = (self.piece_var.get() or f'piece_{idx}')
                pieces_state = self.sidecar.data.get('pieces', {})
                pieces_state[key] = pieces_state.get(key, {})
                pieces_state[key]['canvas'] = self.last_canvas_transform
                self.sidecar.data['pieces'] = pieces_state
                self.sidecar.save()
        except Exception:
            pass
        # redraw
        self.draw_piece(idx)

    def on_mouse_wheel(self, event):
        # Zoom centered at mouse pointer
        try:
            if not self.last_canvas_transform:
                return
            # Windows: event.delta is multiples of 120
            factor = 1.0
            try:
                factor = 1.0 + (event.delta / 1200.0)  # small increments
            except Exception:
                factor = 1.1
            # clamp
            if factor <= 0:
                factor = 0.9
            cx, cy = event.x, event.y
            wx, wy = self.screen_to_world(cx, cy)
            # update scale
            old = self.last_canvas_transform
            new_scale = old['scale'] * factor
            # recompute minx/miny so (wx,wy) stays under cursor
            new_minx = wx - (cx - 10) / new_scale
            new_miny = wy - (cy - 10) / new_scale
            old['scale'] = new_scale
            old['minx'] = new_minx
            old['miny'] = new_miny
            # persist and redraw
            # determine current piece index
            try:
                name = self.piece_var.get()
                idx = 0
                for i,p in enumerate(self.pieces):
                    if (p.get('name') or f'piece_{i}') == name:
                        idx = i; break
            except Exception:
                idx = 0
            self.update_transform_and_redraw(idx)
        except Exception:
            pass

    def on_pan_start(self, event):
        # record pan start state
        try:
            self._pan_state = {'x': event.x, 'y': event.y, 'minx': self.last_canvas_transform.get('minx', 0.0), 'miny': self.last_canvas_transform.get('miny', 0.0), 'scale': self.last_canvas_transform.get('scale', 1.0)}
        except Exception:
            self._pan_state = None

    def _compute_and_display_selection(self):
        out_lines = []
        sel_infos = []
        for it in self._selected_items:
            inf = self._canvas_map.get(it)
            if not inf: continue
            if inf[0] == 'vert':
                _, pi, pth, vi = inf
                coord = self.pieces[pi]['paths'][pth]['points'][vi]
                sel_infos.append((pi, pth, vi, coord))
            elif inf[0] == 'ctrl':
                _, pi, pth, seg_idx, which = inf
                seg = self.pieces[pi]['paths'][pth]['segs'][seg_idx]
                if which == 'p1': coord = seg[2]
                else: coord = seg[3]
                # find nearest vi
                pts = self.pieces[pi]['paths'][pth]['points']
                min_d = 1e12; nvi = 0
                for vi2, wp in enumerate(pts):
                    dx = wp[0]-coord[0]; dy = wp[1]-coord[1]
                    d = (dx*dx+dy*dy)**0.5
                    if d < min_d:
                        min_d = d; nvi = vi2
                sel_infos.append((pi, pth, nvi, coord))
        for i in range(len(sel_infos)):
            coord = sel_infos[i][3]
            out_lines.append(f'{coord[0]:.3f}\t{coord[1]:.3f}')
            if i < len(sel_infos)-1:
                a = sel_infos[i]; b = sel_infos[i+1]
                if a[0]==b[0] and a[1]==b[1]:
                    pts = self.pieces[a[0]]['paths'][a[1]]['points']
                    la = a[2]; lb = b[2]
                    length = 0.0
                    if la != lb:
                        n = len(pts)
                        j = la
                        while j != lb:
                            kidx = (j+1) % n
                            dx = pts[kidx][0]-pts[j][0]; dy = pts[kidx][1]-pts[j][1]
                            length += (dx*dx+dy*dy)**0.5
                            j = kidx
                    out_lines.append(f'{length:.3f} mm')
                else:
                    out_lines.append('N/A (different paths)')
        self.coords_text.delete('1.0', 'end')
        self.coords_text.insert('1.0', '\n'.join(out_lines))

    def on_pan_move(self, event):
        try:
            if not self._pan_state:
                return
            dx = event.x - self._pan_state['x']
            dy = event.y - self._pan_state['y']
            # convert pixel delta to world mm
            scale = self._pan_state.get('scale', 1.0)
            dmx = dx / scale
            dmy = dy / scale
            new_minx = self._pan_state['minx'] - dmx
            new_miny = self._pan_state['miny'] - dmy
            self.last_canvas_transform['minx'] = new_minx
            self.last_canvas_transform['miny'] = new_miny
            # redraw in place (do not re-save too often)
            try:
                name = self.piece_var.get()
                idx = 0
                for i,p in enumerate(self.pieces):
                    if (p.get('name') or f'piece_{i}') == name:
                        idx = i; break
            except Exception:
                idx = 0
            # redraw without saving every motion
            self.draw_piece(idx)
        except Exception:
            pass

    def on_pan_end(self, event):
        try:
            # finalize and save
            try:
                name = self.piece_var.get()
                idx = 0
                for i,p in enumerate(self.pieces):
                    if (p.get('name') or f'piece_{i}') == name:
                        idx = i; break
            except Exception:
                idx = 0
            self.update_transform_and_redraw(idx)
        except Exception:
            pass

    def autosave(self):
        # save app window geometry
        try:
            geom = self.root.winfo_geometry()
            self.app_state['window_geometry'] = geom
            # save sash position if available
            try:
                if hasattr(self, 'paned') and self.paned:
                    try:
                        x,y = self.paned.sash_coord(0)
                        self.app_state['sash_x'] = x
                    except Exception:
                        pass
            except Exception:
                pass
            save_state(self.app_state)
        except Exception:
            pass

        # save sidecar for current file
        try:
            if self.sidecar:
                # ensure last_selected exists
                if 'last_selected' not in self.sidecar.data and hasattr(self, 'piece_var'):
                    self.sidecar.data['last_selected'] = self.piece_var.get()
                self.sidecar.save()
        except Exception:
            pass

        # schedule next autosave
        try:
            self.root.after(2000, self.autosave)
        except Exception:
            pass


if __name__ == '__main__':
    root = tk.Tk()
    app = App(root)
    root.mainloop()
