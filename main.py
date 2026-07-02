import pygame
import random
import math
import os
import sys

os.environ['SDL_ANDROID_TRAP_BACK_BUTTON'] = '1'

def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

pygame.init()
pygame.display.set_caption("War")


class Game:
    def __init__(self):
        # ---- ეკრანი + render surface ----
        self.screen  = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
        self.W_real, self.H_real = self.screen.get_size()

        # შიდა render ნახევარ რეზოლუციაზე — ეს ყველაზე დიდი სიჩქარის მოგება
        # მაგ. 1080x2340 → 540x1170 → 4x ნაკლები pixel სამუშაო
        self.SCALE = 2
        self.W     = self.W_real // self.SCALE
        self.H     = self.H_real // self.SCALE
        self.surf  = pygame.Surface((self.W, self.H))

        # ---- კონსტანტები ----
        self.SHOOT_DELAY    = 350
        self.INVINCIBILITY  = 400
        self.SPAWN_INTERVAL = 1400   # უფრო ხშირი spawn
        self.MIN_SPAWN      = 600
        self.HEAL_AMOUNT    = 15
        self.EXPLOSION_CNT  = 4
        self.PLAYER_HP      = 100
        self.MAX_ENEMIES    = 9      # უფრო მეტი მტერი
        self.MAX_BULLETS    = 35
        self.MAX_E_BULLETS  = 25

        # ---- სურათების ჩატვირთვა (render ზომაზე!) ----
        U = min(self.W // 7, self.H // 10)
        self.p_img  = self._load("player.png",     U,          int(U*0.85))
        self.s_img  = self._load("shooter.png",    U,          U)
        self.r_img  = self._load("enemy.png",      int(U*0.9), int(U*0.75))
        self.b_img  = self._load("boss.png",       U*2,        U*2)
        self.m_img  = self._load("medical.png",    int(U*0.6), int(U*0.6))
        self.o_img  = self._load("bomb.png",       int(U*0.7), int(U*0.7))
        self.pb_img = self._load("playerammo.png", int(U*0.3), int(U*0.5))
        self.eb_img = self._load("anamyammo.png",  int(U*0.4), int(U*0.4))
        self.bg_img = pygame.transform.scale(
            pygame.image.load(resource_path("walpher.png.webp")).convert(),
            (self.W, self.H))  # render ზომა, არა ეკრანის

        # ---- შრიფტები (render ზომისთვის) ----
        self.clock  = pygame.time.Clock()
        self.font_l = pygame.font.SysFont("Arial", 20, bold=True)
        self.font_m = pygame.font.SysFont("Arial", 15)
        self.font_s = pygame.font.SysFont("Arial", 11)
        self.font_lv = pygame.font.SysFont("Arial", 17, bold=True)  # ლეველ ბეჯი

        # ---- ღილაკები (render კოორდინატებში) ----
        BW  = self.W // 6
        BH  = self.H // 14
        pad = 6
        bx  = self.W - BW - pad
        self.BTN_PAUSE  = pygame.Rect(bx, pad,                  BW, BH)
        self.BTN_EXIT   = pygame.Rect(bx, pad + BH + pad,       BW, BH)
        self.BTN_MENU   = pygame.Rect(bx, pad + (BH+pad)*2,     BW, BH)
        self.BTN_SPREAD = pygame.Rect(pad, self.H - BH - pad,   BW, BH)

        # ---- ღილაკების pre-render (ერთხელ) ----
        fz = max(9, int(BH * 0.4))
        self.font_btn  = pygame.font.SysFont("Arial", fz, bold=True)
        self._btn_surfs = {}
        for text, color in [
            ("PAUSE",  (65,65,65)),
            ("EXIT",   (155,25,25)),
            ("MENU",   (150,50,50)),
            ("SPREAD", (65,65,65)),
            ("SPREAD", (0,150,0)),
        ]:
            self._prebake_btn(BW, BH, text, color)

        # ---- pre-created overlays (render ზომა) ----
        self.pause_overlay = pygame.Surface((self.W, self.H), pygame.SRCALPHA)
        self.pause_overlay.fill((0, 0, 0, 130))
        self.lb_rect = pygame.Rect(30, self.H//2 - 14, self.W - 60, 28)

        # ---- ტექსტის კეში ----
        self._hp_surf = None;  self._hp_val  = -999
        self._lv_surf = None;  self._lv_val  = -1
        self._sc_surf = None;  self._sc_val  = -1
        self._msg_surf = None

        # ---- მდგომარეობა ----
        self.running        = True
        self.selection_mode = True
        self.game_over      = False
        self.win_mode       = False
        self.paused         = False
        self.spread_mode    = False
        self.is_loading     = False
        self.loading_start  = 0
        self.unlocked_level = self._load_save()
        self.current_level  = 1
        self.score          = 0
        self.total_score    = 0
        self.last_spawn     = 0
        self.boss           = None
        self.level_msg      = ""
        self.msg_timer      = 0

        # ---- სპრაიტ ჯგუფები ----
        self.all_sprites   = pygame.sprite.Group()
        self.bullets       = pygame.sprite.Group()
        self.enemy_bullets = pygame.sprite.Group()
        self.enemies       = pygame.sprite.Group()
        self.bosses        = pygame.sprite.Group()
        self.heals         = pygame.sprite.Group()
        self.obstacles     = pygame.sprite.Group()
        self.player        = None

        # ---- particles (Surface შექმნა 0) ----
        self.particles = []

        self.boss_bar_colors = [
            (220,0,0),(255,140,0),(220,220,0),(0,200,0),(0,200,220)
        ]

    # ------------------------------------------------------------------
    def _prebake_btn(self, w, h, text, color):
        surf = pygame.Surface((w, h))
        pygame.draw.rect(surf, color, surf.get_rect(), border_radius=8)
        t = self.font_btn.render(text, True, (255, 255, 255))
        surf.blit(t, ((w - t.get_width())//2, (h - t.get_height())//2))
        self._btn_surfs[(text, color)] = surf

    def _draw_btn(self, rect, color, text):
        key = (text, color)
        if key not in self._btn_surfs:
            self._prebake_btn(rect.w, rect.h, text, color)
        self.surf.blit(self._btn_surfs[key], rect.topleft)

    # ------------------------------------------------------------------
    def _load(self, name, w, h):
        img = pygame.image.load(resource_path(name)).convert_alpha()
        return pygame.transform.scale(img, (max(1,w), max(1,h)))

    def _save(self, lv):
        try:
            with open("save.txt", "w") as f: f.write(str(lv))
        except Exception: pass

    def _load_save(self):
        try:
            with open("save.txt") as f:
                return max(1, min(100, int(f.read().strip())))
        except Exception: return 1

    # ------------------------------------------------------------------
    def reset_game(self, lv):
        for g in [self.all_sprites, self.bullets, self.enemy_bullets,
                  self.enemies, self.bosses, self.heals, self.obstacles]:
            g.empty()
        self.particles.clear()
        self.game_over     = False
        self.win_mode      = False
        self.boss          = None
        self.current_level = lv
        self.score         = 0
        self.total_score   = 0
        self.player        = Player(self.W//2, self.H-80, self)
        self.all_sprites.add(self.player)
        self.is_loading    = True
        self.loading_start = pygame.time.get_ticks()
        self.last_spawn    = pygame.time.get_ticks()
        self._hp_val       = -999
        self._lv_val       = -1
        self._sc_val       = -1

    # ------------------------------------------------------------------
    def run(self):
        while self.running:
            self.events()
            self.update()
            self.draw()
            self.clock.tick(30)
        pygame.quit()

    # ------------------------------------------------------------------
    def _screen_to_render(self, x, y):
        """ეკრანის კოორდინატები → render surface კოორდინატები."""
        return x // self.SCALE, y // self.SCALE

    def events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                self.running = False
            # ᲛᲮᲝᲚᲝᲓ MOUSEBUTTONDOWN — Pydroid touch → mouse event
            # FINGERDOWN ამოღებულია: ორმაგ გამოძახებას იწვევდა
            elif event.type == pygame.MOUSEBUTTONDOWN:
                rx, ry = self._screen_to_render(*event.pos)
                self._handle_tap(rx, ry)

    def _handle_tap(self, mx, my):
        if not self.selection_mode and not self.game_over and not self.win_mode:
            if self.BTN_PAUSE.collidepoint(mx, my):
                self.paused = not self.paused; return
            if self.BTN_EXIT.collidepoint(mx, my):
                self.running = False; return
            if self.paused and self.BTN_MENU.collidepoint(mx, my):
                self.selection_mode = True; self.paused = False; return
            if self.BTN_SPREAD.collidepoint(mx, my):
                self.spread_mode = not self.spread_mode; return

        if self.selection_mode:
            rst = pygame.Rect(14, self.H-44, 90, 34)
            if rst.collidepoint(mx, my):
                self.unlocked_level = 1; self._save(1); return
            cols, pad2 = 10, 10
            cw = (self.W - pad2*2) // cols
            ch = (self.H - 110) // 10
            sy = 56
            for i in range(1, 101):
                c = (i-1) % cols
                r = (i-1) // cols
                rect = pygame.Rect(pad2+c*cw, sy+r*ch, cw-4, ch-4)
                if rect.collidepoint(mx, my) and i <= self.unlocked_level:
                    self.reset_game(i); self.selection_mode = False; return

        if self.game_over or self.win_mode:
            self.selection_mode = True

    # ------------------------------------------------------------------
    def update(self):
        if (not self.selection_mode and not self.game_over and
                not self.win_mode and not self.is_loading and not self.paused):
            self._spawn()
            self._combat()
            self._level_check()
            self.all_sprites.update()
            self._update_particles()

            # ტყვიების ლიმიტი
            if len(self.bullets) > self.MAX_BULLETS:
                for b in list(self.bullets)[:4]:
                    b.kill()
            if len(self.enemy_bullets) > self.MAX_E_BULLETS:
                for b in list(self.enemy_bullets)[:4]:
                    b.kill()

    def _update_particles(self):
        alive = []
        for p in self.particles:
            p['x'] += p['vx']
            p['y'] += p['vy']
            p['life'] -= 1
            if p['life'] > 0:
                alive.append(p)
        self.particles = alive

    # ------------------------------------------------------------------
    def _spawn(self):
        lv = self.current_level
        if lv % 5 == 0 and not self.bosses and self.boss is None:
            self.boss = Boss(lv, self)
            self.all_sprites.add(self.boss); self.bosses.add(self.boss)

        delay = max(self.MIN_SPAWN, self.SPAWN_INTERVAL - lv*10)
        if not self.bosses and pygame.time.get_ticks() - self.last_spawn > delay:
            if len(self.enemies) <= self.MAX_ENEMIES - 3:   # 3 ემატება → არ გადააჭარბოს max-ს
                s  = Enemy("shooter", lv, self)
                r  = Enemy("rusher",  lv, self)
                r2 = Enemy("rusher",  lv, self)
                self.all_sprites.add(s, r, r2); self.enemies.add(s, r, r2)
            if lv >= 3 and random.random() < 0.08:
                obs = Obstacle(lv, self)
                self.all_sprites.add(obs); self.obstacles.add(obs)
            self.last_spawn = pygame.time.get_ticks()

    # ------------------------------------------------------------------
    def _combat(self):
        pygame.sprite.groupcollide(self.obstacles, self.bullets, True, True)

        for h in pygame.sprite.groupcollide(self.enemies, self.bullets, False, True):
            h.hp -= 1
            if h.hp <= 0:
                h.kill()
                self._explode(h.rect.centerx, h.rect.centery, (255,80,0))
                self.score += 1
                self.total_score += 1
                if random.random() < 0.2:
                    heal = Heal(h.rect.centerx, h.rect.centery, self)
                    self.heals.add(heal); self.all_sprites.add(heal)

        for b in pygame.sprite.groupcollide(self.bosses, self.bullets, False, True):
            b.hp -= 1
            if b.hp <= 0:
                self._explode(b.rect.centerx, b.rect.centery, (255,255,0))
                b.kill(); self.boss = None
                if self.current_level == 100:
                    self.win_mode = True; self.msg_timer = pygame.time.get_ticks()
                else:
                    self.score = 0; self.current_level += 1

        if self.player:
            if pygame.sprite.spritecollide(self.player, self.heals, True):
                self.player.hp = min(self.PLAYER_HP, self.player.hp + self.HEAL_AMOUNT)
            now = pygame.time.get_ticks()
            hb  = pygame.sprite.spritecollide(self.player, self.enemy_bullets, True)
            he  = pygame.sprite.spritecollide(self.player, self.enemies,       False)
            ho  = pygame.sprite.spritecollide(self.player, self.obstacles,     False)
            if (hb or he or ho) and now - self.player.last_hit > self.INVINCIBILITY:
                self.player.hp -= 15
                self.player.last_hit = now
                if self.player.hp <= 0:
                    self.game_over = True

    # ------------------------------------------------------------------
    def _level_check(self):
        needed = 50 + self.current_level * 5
        if self.score >= needed and self.current_level % 5 != 0:
            if self.current_level >= self.unlocked_level and self.unlocked_level < 100:
                self.unlocked_level += 1; self._save(self.unlocked_level)
            self.score = 0; self.current_level += 1
            self.level_msg  = f"Level {self.current_level}!"
            self.msg_timer  = pygame.time.get_ticks()
            self._msg_surf  = self.font_l.render(self.level_msg, True, (255,220,0))

    def _explode(self, x, y, color):
        for _ in range(self.EXPLOSION_CNT):
            self.particles.append({
                'x': x, 'y': y,
                'vx': random.uniform(-3, 3),
                'vy': random.uniform(-3, 3),
                'life': random.randint(8, 16),
                'color': color,
                'size': random.randint(3, 7),
            })

    # ------------------------------------------------------------------
    def draw(self):
        # ყველაფერი self.surf-ზე იხატება (ნახევარი რეზოლუცია)
        s = self.surf

        if not self.selection_mode and not self.game_over and not self.win_mode:
            s.blit(self.bg_img, (0, 0))
        else:
            s.fill((8, 8, 22))

        # =================== SELECTION ===================
        if self.selection_mode:
            t = self.font_l.render("Level Select", True, (255,255,255))
            s.blit(t, (self.W//2 - t.get_width()//2, 22))
            cols, pad2 = 10, 10
            cw = (self.W - pad2*2) // cols
            ch = (self.H - 110) // 10
            sy = 56
            for i in range(1, 101):
                col = (i-1) % cols
                row = (i-1) // cols
                r   = pygame.Rect(pad2+col*cw, sy+row*ch, cw-4, ch-4)
                unlocked = i <= self.unlocked_level
                c   = (45,95,195) if unlocked else (22,22,38)
                tc  = (255,255,255) if unlocked else (55,55,75)
                pygame.draw.rect(s, c, r, border_radius=6)
                num = self.font_s.render(str(i), True, tc)
                s.blit(num, (r.x+(r.w-num.get_width())//2, r.y+(r.h-num.get_height())//2))
            rst = pygame.Rect(14, self.H-44, 90, 34)
            pygame.draw.rect(s, (170,25,25), rst, border_radius=8)
            rt = self.font_m.render("RESET", True, (255,255,255))
            s.blit(rt, (rst.x+(rst.w-rt.get_width())//2, rst.y+(rst.h-rt.get_height())//2))

        # =================== LOADING ===================
        elif self.is_loading:
            elapsed = pygame.time.get_ticks() - self.loading_start
            prog    = min(elapsed / 1200, 1.0)
            bw      = int((self.W - 60) * prog)
            pygame.draw.rect(s, (35,35,35), self.lb_rect, border_radius=10)
            if bw > 0:
                pygame.draw.rect(s, (0,170,75),
                                 (30, self.lb_rect.y, bw, 28), border_radius=10)
            lt = self.font_l.render(f"Level {self.current_level}", True, (255,255,255))
            s.blit(lt, (self.W//2-lt.get_width()//2, self.H//2-50))
            if elapsed > 1200:
                self.is_loading = False

        # =================== GAME OVER ===================
        elif self.game_over:
            t = self.font_l.render("GAME OVER", True, (255,55,55))
            sub = self.font_m.render("Tap to return", True, (200,200,200))
            s.blit(t,   (self.W//2-t.get_width()//2,   self.H//2-25))
            s.blit(sub, (self.W//2-sub.get_width()//2, self.H//2+15))

        # =================== WIN ===================
        elif self.win_mode:
            t = self.font_l.render("VICTORY!", True, (255,215,0))
            s.blit(t, (self.W//2-t.get_width()//2, self.H//2))
            if pygame.time.get_ticks() - self.msg_timer > 3000:
                self.win_mode = False; self.selection_mode = True

        # =================== GAMEPLAY ===================
        elif self.player:
            self.all_sprites.draw(s)

            # particles
            for p in self.particles:
                sz = max(1, p['size'] * p['life'] // 16)
                pygame.draw.circle(s, p['color'], (int(p['x']), int(p['y'])), sz)

            # მტრის HP
            for e in self.enemies:
                r = e.hp / e.max_hp
                pygame.draw.rect(s, (160,0,0),   (e.rect.x, e.rect.y-7, 50, 4), border_radius=2)
                pygame.draw.rect(s, (0,200,0),   (e.rect.x, e.rect.y-7, int(50*r), 4), border_radius=2)

            # ბოსი HP — y=64 (HUD კომპლექტის ქვემოთ, overlap-ი აღარ არის)
            if self.boss and self.boss.alive():
                ci = min(self.boss.level//10, 4)
                BAR_X  = self.W // 5          # მარჯვნივ, HUD-ს გვერდით
                BAR_W2 = self.W - BAR_X - 10
                bw = int(BAR_W2 * (self.boss.hp / self.boss.max_hp))
                pygame.draw.rect(s, (35,35,35), (BAR_X, 8, BAR_W2, 14), border_radius=6)
                if bw > 0:
                    pygame.draw.rect(s, self.boss_bar_colors[ci], (BAR_X, 8, bw, 14), border_radius=6)
                bt = self.font_s.render("BOSS", True, (255,255,255))
                s.blit(bt, (BAR_X + BAR_W2//2 - bt.get_width()//2, 9))

            # ========= ზედა მარცხენა HUD =========
            HUD_X = 6
            # --- ლეველი ბეჯი ---
            if self.current_level != self._lv_val:
                self._lv_val  = self.current_level
                lv_txt = f"LEVEL  {self.current_level}"
                self._lv_surf = self.font_lv.render(lv_txt, True, (255, 230, 80))
            lw = self._lv_surf.get_width() + 14
            lh = self._lv_surf.get_height() + 6
            pygame.draw.rect(s, (20, 20, 20), (HUD_X - 2, 5, lw, lh), border_radius=7)
            pygame.draw.rect(s, (80, 60, 0),  (HUD_X - 2, 5, lw, lh), border_radius=7, width=2)
            s.blit(self._lv_surf, (HUD_X + 5, 8))
            HUD_Y2 = 5 + lh + 5

            # --- HP ბარი ---
            hp    = max(0, self.player.hp)
            ratio = hp / self.PLAYER_HP
            hc    = (0, 200, 0) if ratio > 0.5 else (255, 150, 0) if ratio > 0.25 else (220, 0, 0)
            BAR_W = 110
            pygame.draw.rect(s, (30, 30, 30), (HUD_X, HUD_Y2, BAR_W, 11), border_radius=4)
            if ratio > 0:
                pygame.draw.rect(s, hc, (HUD_X, HUD_Y2, int(BAR_W * ratio), 11), border_radius=4)
            if hp != self._hp_val:
                self._hp_val  = hp
                self._hp_surf = self.font_s.render(f"HP {hp}", True, (255, 255, 255))
            s.blit(self._hp_surf, (HUD_X + 2, HUD_Y2 + 1))
            HUD_Y3 = HUD_Y2 + 15

            # --- ქულები ---
            if self.total_score != self._sc_val:
                self._sc_val  = self.total_score
                self._sc_surf = self.font_s.render(f"* {self.total_score}", True, (255, 215, 0))
            s.blit(self._sc_surf, (HUD_X, HUD_Y3))

            # Level-up შეტყობინება
            if self._msg_surf and pygame.time.get_ticks() - self.msg_timer < 2000:
                mt  = self._msg_surf
                mx2 = self.W//2 - mt.get_width()//2
                pygame.draw.rect(s, (0,0,0), (mx2-8, self.H//2-22, mt.get_width()+16, mt.get_height()+8))
                s.blit(mt, (mx2, self.H//2-18))

            # ღილაკები
            self._draw_btn(self.BTN_PAUSE,  (65,65,65),  "PAUSE")
            self._draw_btn(self.BTN_EXIT,   (155,25,25), "EXIT")
            self._draw_btn(self.BTN_SPREAD, (0,150,0) if self.spread_mode else (65,65,65), "SPREAD")
            if self.paused:
                self._draw_btn(self.BTN_MENU, (150,50,50), "MENU")
                s.blit(self.pause_overlay, (0, 0))
                pt = self.font_l.render("PAUSED", True, (255,255,255))
                s.blit(pt, (self.W//2-pt.get_width()//2, self.H//2))

        # ---- render surface → ეკრანი (ერთი scale) ----
        pygame.transform.scale(self.surf, (self.W_real, self.H_real), self.screen)
        pygame.display.flip()


# ==============================================================
class Player(pygame.sprite.Sprite):
    def __init__(self, x, y, game):
        super().__init__()
        self.game      = game
        self.image     = game.p_img
        self.rect      = self.image.get_rect(center=(x, y))
        self.hp        = game.PLAYER_HP
        self.last_shot = pygame.time.get_ticks()
        self.last_hit  = pygame.time.get_ticks()
        self.zone_top  = int(game.H * 0.55)

    def update(self):
        # mouse.get_pos() → render კოორდინატები
        sx, sy = pygame.mouse.get_pos()
        mx = sx // self.game.SCALE
        my = sy // self.game.SCALE
        self.rect.centerx = max(30, min(self.game.W-30, mx))
        self.rect.centery  = max(self.zone_top, min(self.game.H-30, my))
        now = pygame.time.get_ticks()
        if now - self.last_shot > self.game.SHOOT_DELAY:
            self._shoot(); self.last_shot = now

    def _shoot(self):
        g = self.game
        if g.spread_mode:
            for ax in [-0.20, -0.07, 0.07, 0.20]:
                b = Bullet(self.rect.centerx, self.rect.top, 14, int(ax*8), g.pb_img, g)
                g.all_sprites.add(b); g.bullets.add(b)
        else:
            b = Bullet(self.rect.centerx, self.rect.top, 16, 0, g.pb_img, g)
            g.all_sprites.add(b); g.bullets.add(b)


# ==============================================================
class Bullet(pygame.sprite.Sprite):
    def __init__(self, x, y, vy, vx, image, game):
        super().__init__()
        self.game  = game
        self.image = image
        self.rect  = self.image.get_rect(centerx=x, bottom=y)
        self.vy    = vy
        self.vx    = vx

    def update(self):
        self.rect.y -= self.vy
        self.rect.x += self.vx
        if (self.rect.bottom < 0 or self.rect.top > self.game.H or
                self.rect.right < 0 or self.rect.left > self.game.W):
            self.kill()


# ==============================================================
class Enemy(pygame.sprite.Sprite):
    def __init__(self, mode, lv, game):
        super().__init__()
        self.game      = game
        self.mode      = mode
        self.image     = game.s_img if mode == "shooter" else game.r_img
        self.rect      = self.image.get_rect(x=random.randint(0, game.W-60), y=-50)
        self.max_hp    = 4 + lv//2
        self.hp        = self.max_hp
        self.speed     = 2.0 + lv*0.13   # სწრაფი
        self.lv        = lv
        self.start_x   = self.rect.x
        self.spawn_t   = pygame.time.get_ticks()
        self.last_shot = pygame.time.get_ticks()

    def update(self):
        g = self.game; now = pygame.time.get_ticks()
        if self.mode == "shooter":
            if now - self.spawn_t > 8000:
                self.kill(); return
            if self.rect.y < 60:
                self.rect.y += max(1, int(self.speed*0.5))
            delay = max(400, 1300 - self.lv*15)   # სწრაფი სროლა
            if now - self.last_shot > delay:
                # shooter ლეველის მიხედვით სრობს: 1 → 1 ტყვია, 6+ → 2 ტყვია, 12+ → 3
                n_bullets = 1 + self.lv // 6
                spread = 0.14
                for i in range(n_bullets):
                    ox = (i - (n_bullets-1)/2) * spread
                    b = Bullet(self.rect.centerx, self.rect.bottom,
                               -9 - self.lv*0.1, ox*6, g.eb_img, g)
                    g.all_sprites.add(b); g.enemy_bullets.add(b)
                self.last_shot = now
        else:
            pat = (self.lv//5) % 3
            if pat == 0:
                self.rect.y += self.speed + 1.5
            elif pat == 1:
                self.rect.y += self.speed + 1.5
                self.rect.x += math.sin(self.rect.y/18) * (5 + self.lv*0.15)
            else:
                self.rect.y += self.speed + 1.2
                self.rect.x  = self.start_x + math.cos(self.rect.y/28)*(45+self.lv)
            self.rect.x = max(0, min(g.W-60, self.rect.x))
            if self.rect.top > g.H:
                self.kill()


# ==============================================================
class Boss(pygame.sprite.Sprite):
    def __init__(self, lv, game):
        super().__init__()
        self.game      = game
        self.level     = lv
        self.image     = game.b_img
        self.rect      = self.image.get_rect(centerx=game.W//2, y=30)
        self.max_hp    = 300 + lv*12
        self.hp        = self.max_hp
        self.speed     = 2 + lv//10
        self.dir       = 1
        self.last_shot = pygame.time.get_ticks()

    def update(self):
        self.rect.x += self.speed * self.dir
        if self.rect.right > self.game.W or self.rect.left < 0:
            self.dir *= -1
        now = pygame.time.get_ticks()
        interval = max(900, 1200 - self.level*4)
        if now - self.last_shot > interval:
            n = 6 + (self.level//10)*2
            for i in range(n):
                a = i * (2*math.pi/n)
                b = Bullet(self.rect.centerx, self.rect.centery,
                           -math.sin(a)*4, math.cos(a)*4, self.game.eb_img, self.game)
                self.game.all_sprites.add(b); self.game.enemy_bullets.add(b)
            self.last_shot = now


# ==============================================================
class Obstacle(pygame.sprite.Sprite):
    def __init__(self, lv, game):
        super().__init__()
        self.game  = game
        self.image = game.o_img
        self.rect  = self.image.get_rect(x=random.randint(0, game.W-50), y=-50)
        self.speed = 2.2 + lv*0.15

    def update(self):
        self.rect.y += self.speed
        if self.rect.top > self.game.H: self.kill()


# ==============================================================
class Heal(pygame.sprite.Sprite):
    def __init__(self, x, y, game):
        super().__init__()
        self.game  = game
        self.image = game.m_img
        self.rect  = self.image.get_rect(center=(x, y))

    def update(self):
        self.rect.y += 2
        if self.rect.top > self.game.H: self.kill()


# ==============================================================
if __name__ == "__main__":
    game = Game()
    game.run()
