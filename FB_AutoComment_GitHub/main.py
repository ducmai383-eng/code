
import os, re, json, time, random, threading, zipfile
from io import BytesIO
from datetime import datetime

import requests
from kivy.app import App
from kivy.clock import Clock
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.uix.tabbedpanel import TabbedPanel, TabbedPanelItem
from kivy.uix.scrollview import ScrollView
from kivy.uix.popup import Popup
from kivy.uix.filechooser import FileChooserListView

API_VERSION = "v21.0"
BASE_URL = f"https://graph.facebook.com/{API_VERSION}"
EMOJIS = ["😊","❤️","👍","🔥","💯","🎉","✨","🙌","😍","🥰","😘","💪","👏","🤩","😇","🌟"]

class FBApp(App):
    def build(self):
        self.title = "FB Auto Comment Android"
        self.token_list = []
        self.post_links = []
        self.current_groups = []
        self.running = False
        self.stop_flags = {}
        self.status = {}
        self.lock = threading.Lock()
        self.config_file = os.path.join(self.user_data_dir, "config.json")
        self.log_file = None

        root = BoxLayout(orientation="vertical", padding=dp(8), spacing=dp(6))
        self.tabs = TabbedPanel(do_default_tab=False)

        self.tabs.add_widget(self.make_config_tab())
        self.tabs.add_widget(self.make_run_tab())
        self.tabs.add_widget(self.make_split_tab())

        root.add_widget(self.tabs)
        return root

    def lbl(self, text="", size=16):
        return Label(text=text, font_size=dp(size), size_hint_y=None, height=dp(38))

    def make_config_tab(self):
        tab = TabbedPanelItem(text="Cấu hình")
        outer = BoxLayout(orientation="vertical", spacing=dp(5))

        outer.add_widget(self.lbl("TOKEN", 17))
        self.token_box = TextInput(multiline=True, hint_text="Mỗi dòng 1 token", size_hint_y=None, height=dp(110))
        outer.add_widget(self.token_box)

        row = BoxLayout(size_hint_y=None, height=dp(45), spacing=dp(5))
        row.add_widget(Button(text="Nạp token", on_press=lambda *_: self.load_tokens()))
        row.add_widget(Button(text="Test token", on_press=lambda *_: self.test_all_tokens()))
        row.add_widget(Button(text="Xóa token", on_press=lambda *_: self.token_box.text=""))
        outer.add_widget(row)

        outer.add_widget(self.lbl("Delay mỗi link (giây)", 14))
        self.delay_input = TextInput(text="300", multiline=False, input_filter="float",
                                     size_hint_y=None, height=dp(42))
        outer.add_widget(self.delay_input)

        outer.add_widget(self.lbl("Nội dung bình luận", 14))
        self.comment_input = TextInput(multiline=True, hint_text="Nhập nội dung bình luận",
                                       size_hint_y=None, height=dp(110))
        outer.add_widget(self.comment_input)

        outer.add_widget(self.lbl("URL ảnh đính kèm (tùy chọn)", 14))
        self.image_input = TextInput(multiline=False, hint_text="https://...",
                                     size_hint_y=None, height=dp(42))
        outer.add_widget(self.image_input)

        outer.add_widget(self.lbl("Link bài viết (mỗi dòng 1 link)", 14))
        self.links_input = TextInput(multiline=True, hint_text="Dán danh sách link Facebook",
                                     size_hint_y=None, height=dp(130))
        outer.add_widget(self.links_input)

        row2 = BoxLayout(size_hint_y=None, height=dp(45), spacing=dp(5))
        row2.add_widget(Button(text="Load links", on_press=lambda *_: self.load_posts()))
        row2.add_widget(Button(text="Lưu cấu hình", on_press=lambda *_: self.save_config()))
        outer.add_widget(row2)

        return tab

    def make_run_tab(self):
        tab = TabbedPanelItem(text="Chạy")
        outer = BoxLayout(orientation="vertical", spacing=dp(5))

        row = BoxLayout(size_hint_y=None, height=dp(50), spacing=dp(5))
        self.run_btn = Button(text="▶ CHẠY", on_press=lambda *_: self.run_multi())
        self.stop_btn = Button(text="⏹ DỪNG", on_press=lambda *_: self.stop_all())
        row.add_widget(self.run_btn)
        row.add_widget(self.stop_btn)
        outer.add_widget(row)

        self.global_status = self.lbl("Sẵn sàng...", 14)
        outer.add_widget(self.global_status)

        self.status_view = TextInput(readonly=True, multiline=True)
        outer.add_widget(self.status_view)
        return tab

    def make_split_tab(self):
        tab = TabbedPanelItem(text="Chia Link")
        outer = BoxLayout(orientation="vertical", spacing=dp(5))

        outer.add_widget(self.lbl("Danh sách link", 14))
        self.split_input = TextInput(multiline=True, hint_text="Mỗi dòng 1 link")
        outer.add_widget(self.split_input)

        grid = GridLayout(cols=2, size_hint_y=None, height=dp(90), spacing=dp(5))
        grid.add_widget(self.lbl("Min", 14))
        self.min_input = TextInput(text="10", multiline=False, input_filter="int")
        grid.add_widget(self.min_input)
        grid.add_widget(self.lbl("Max", 14))
        self.max_input = TextInput(text="30", multiline=False, input_filter="int")
        grid.add_widget(self.max_input)
        outer.add_widget(grid)

        row = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(5))
        row.add_widget(Button(text="🔀 CHIA NHÓM", on_press=lambda *_: self.split_groups()))
        row.add_widget(Button(text="📦 XUẤT ZIP", on_press=lambda *_: self.export_zip()))
        outer.add_widget(row)

        self.groups_view = TextInput(readonly=True, multiline=True)
        outer.add_widget(self.groups_view)
        return tab

    # ---------- logic ported from desktop version ----------

    def extract_post_id(self, url):
        url = url.strip()
        path = url.split("?")[0].split("#")[0]
        query = url.split("?", 1)[1].split("#")[0] if "?" in url else ""

        if "/share/p/" in path:
            try:
                r = requests.head(url, allow_redirects=True, timeout=10,
                                   headers={"User-Agent": "Mozilla/5.0"})
                return self.extract_post_id(r.url)
            except Exception:
                pass

        m = re.search(r'/(\d{10,})/posts/(\d{10,})', path)
        if m: return f"{m.group(1)}_{m.group(2)}"
        m = re.search(r'/groups/(\d{10,})/posts/(\d{10,})', path)
        if m: return f"{m.group(1)}_{m.group(2)}"
        m_story = re.search(r'story_fbid=(\d{10,})', query)
        m_id = re.search(r'[?&]id=(\d{10,})', query)
        if m_story and m_id: return f"{m_id.group(1)}_{m_story.group(1)}"
        if m_story: return m_story.group(1)
        m = re.search(r'fbid=(\d{10,})', query)
        if m: return m.group(1)
        m = re.search(r'[?&]v=(\d{10,})', query)
        if m: return m.group(1)
        if m_id: return m_id.group(1)
        m = re.search(r'/photos/\d+/\d+/(\d{10,})', path)
        if m: return m.group(1)
        m = re.search(r'/(\d{10,}_\d{10,})', path)
        if m: return m.group(1)
        numbers = re.findall(r'\d{15,}', path)
        if numbers: return numbers[-1]
        numbers = re.findall(r'\d{15,}', url)
        if numbers: return numbers[-1]
        return None

    def test_token(self, token):
        try:
            r = requests.get(f"{BASE_URL}/me",
                             params={"fields":"id,name","access_token":token},
                             timeout=15)
            data = r.json()
            if "id" in data:
                return True, f"OK: {data.get('name','Unknown')} (ID:{data['id']})"
            err = data.get("error", {}).get("message", "Phản hồi lạ")
            code = data.get("error", {}).get("code", "")
            return False, f"[{code}] {err[:80]}"
        except Exception as e:
            return False, str(e)[:80]

    def api_comment(self, post_id, message, token, image_url=None):
        try:
            params = {"message": message, "access_token": token}
            if image_url:
                params["attachment_url"] = image_url
            r = requests.post(f"{BASE_URL}/{post_id}/comments",
                              params=params, timeout=30)
            data = r.json()
            if "id" in data:
                return True, data["id"]
            err = data.get("error", {}).get("message", "Phản hồi lạ")
            code = data.get("error", {}).get("code", "")
            return False, f"[{code}] {err[:90]}"
        except Exception as e:
            return False, str(e)[:90]

    def get_post_permalink(self, post_id, token):
        try:
            r = requests.get(f"{BASE_URL}/{post_id}",
                             params={"fields":"permalink_url","access_token":token},
                             timeout=10)
            data = r.json()
            return data.get("permalink_url")
        except Exception:
            return None

    def get_comment_permalink(self, comment_id, token, post_id=None):
        try:
            r = requests.get(f"{BASE_URL}/{comment_id}",
                             params={"fields":"permalink_url","access_token":token},
                             timeout=12)
            data = r.json()
            if data.get("permalink_url"):
                return data["permalink_url"]
        except Exception:
            pass

        if post_id:
            pp = self.get_post_permalink(post_id, token)
            part = comment_id.split("_")[-1] if "_" in comment_id else comment_id
            if pp:
                return pp.split("?")[0].split("#")[0] + f"?comment_id={part}"
            if "_" in post_id:
                page_id, actual = post_id.split("_", 1)
            else:
                page_id = actual = post_id
            return f"https://www.facebook.com/{page_id}/posts/{actual}/?comment_id={part}"
        return f"https://www.facebook.com/permalink.php?comment_id={comment_id}"

    def load_tokens(self):
        self.token_list = [{"token": x.strip(), "nickname": f"Token {i+1}"}
                           for i, x in enumerate(self.token_box.text.splitlines()) if x.strip()]
        self.global_status.text = f"Đã nạp {len(self.token_list)} token"

    def test_all_tokens(self):
        self.load_tokens()
        if not self.token_list:
            self.global_status.text = "Chưa có token"
            return
        threading.Thread(target=self._test_tokens_worker, daemon=True).start()

    def _test_tokens_worker(self):
        out = []
        for item in self.token_list:
            ok, msg = self.test_token(item["token"])
            out.append(f"{item['nickname']}: {'✅' if ok else '❌'} {msg}")
        Clock.schedule_once(lambda *_: self.set_status("\n".join(out)), 0)

    def load_posts(self):
        self.post_links = list(dict.fromkeys(
            x.strip() for x in self.links_input.text.splitlines() if x.strip().startswith("http")
        ))
        good = sum(1 for x in self.post_links if self.extract_post_id(x))
        self.global_status.text = f"Đã load {len(self.post_links)} link | {good} có post_id"

    def run_multi(self):
        if self.running:
            return
        self.load_tokens()
        self.load_posts()
        comment = self.comment_input.text.strip()
        if not self.token_list or not self.post_links or not comment:
            self.global_status.text = "Cần token + link + nội dung bình luận"
            return
        try:
            delay = max(5.0, float(self.delay_input.text or "300"))
        except Exception:
            delay = 300.0

        self.running = True
        self.stop_flags = {x["nickname"]: True for x in self.token_list}
        self.run_btn.disabled = True
        self.log_file = os.path.join(
            self.user_data_dir,
            "comments_done_" + datetime.now().strftime("%Y%m%d_%H%M%S") + ".txt"
        )
        self.set_status("🚀 Đang chạy...")
        image_url = self.image_input.text.strip() or None

        for idx, item in enumerate(self.token_list):
            threading.Thread(
                target=self.worker,
                args=(item, self.post_links[:], comment, delay, image_url),
                daemon=True,
                name=f"Worker-{idx+1}"
            ).start()

    def worker(self, item, links, comment, delay, image_url):
        nick = item["nickname"]
        token = item["token"]
        okc = failc = 0

        for i, link in enumerate(links, 1):
            if not self.running or not self.stop_flags.get(nick, False):
                break

            pid = self.extract_post_id(link)
            if not pid:
                failc += 1
                self.push_status(f"{nick}: ⚠ [{i}] Không lấy được post_id")
                continue

            final = comment + " " + random.choice(EMOJIS)
            ok, result = self.api_comment(pid, final, token, image_url)

            if ok:
                okc += 1
                cmt = self.get_comment_permalink(result, token, pid)
                try:
                    with self.lock:
                        with open(self.log_file, "a", encoding="utf-8") as f:
                            f.write(cmt + "\n")
                except Exception:
                    pass
                self.push_status(f"{nick}: ✅ [{i}/{len(links)}]")
            else:
                failc += 1
                self.push_status(f"{nick}: ❌ {result[:70]}")

            wait = max(5.0, delay * random.uniform(0.85, 1.6))
            for _ in range(int(wait)):
                if not self.running or not self.stop_flags.get(nick, False):
                    break
                time.sleep(1)

        self.push_status(f"{nick}: XONG ✅{okc} ❌{failc}")

    def stop_all(self):
        self.running = False
        for k in self.stop_flags:
            self.stop_flags[k] = False
        self.run_btn.disabled = False
        self.global_status.text = "⏹ Đã yêu cầu dừng"

    def push_status(self, text):
        Clock.schedule_once(lambda *_: self.set_status(text), 0)

    def set_status(self, text):
        self.status_view.text += ("" if not self.status_view.text else "\n") + text

    # ---------- split links ----------

    def split_groups(self):
        links = [x.strip() for x in self.split_input.text.splitlines()
                 if x.strip().startswith("http")]
        try:
            mn, mx = int(self.min_input.text or 10), int(self.max_input.text or 30)
        except Exception:
            self.groups_view.text = "Min/Max không hợp lệ"
            return
        if mn <= 0 or mx < mn:
            self.groups_view.text = "Khoảng nhóm không hợp lệ"
            return

        self.current_groups = []
        n = 1
        while links:
            size = random.randint(mn, mx)
            group = links[:size]
            links = links[size:]
            self.current_groups.append(group)
            n += 1

        self.groups_view.text = "\n\n".join(
            f"Nhóm {i+1} ({len(g)} link)\n" + "\n".join(g)
            for i, g in enumerate(self.current_groups)
        )

    def export_zip(self):
        if not self.current_groups:
            self.groups_view.text = "Chưa có nhóm để xuất"
            return
        path = os.path.join(self.user_data_dir, "nhom_links.zip")
        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
            for i, g in enumerate(self.current_groups, 1):
                z.writestr(f"nhom_{i}.txt", "\n".join(g))
        self.groups_view.text += f"\n\nĐã lưu: {path}"

    def save_config(self):
        data = {
            "delay": self.delay_input.text,
            "comment": self.comment_input.text,
            "image_url": self.image_input.text,
        }
        try:
            with open(self.config_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            self.global_status.text = "Đã lưu cấu hình"
        except Exception as e:
            self.global_status.text = f"Lỗi lưu: {e}"

if __name__ == "__main__":
    FBApp().run()
