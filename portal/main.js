(function () {
  "use strict";

  var root = document.documentElement;
  var prefersReduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  root.classList.add("js");

  /* ------------------------------------------------------------------
     Theme switching (portal palette mirrors SllkGui built-in themes)
     ------------------------------------------------------------------ */
  var THEMES = {
    default: {
      file: "default.png",
      shot: "assets/default.png",
      color: "#0b0f12",
      alt: "SllkGui Default 主题界面截图：深色亚克力窗口、按钮与语义色预览、右侧外观配置面板。",
      caption: "Default 主题 · 界面截图来自仓库 docs/assets，为历史版本界面，仅用于展示主题配色。"
    },
    bright: {
      file: "bright.png",
      shot: "assets/bright.png",
      color: "#f3efe6",
      alt: "SllkGui Bright 主题界面截图：浅色通透窗口、蓝色主按钮、按钮与语义色预览。",
      caption: "Bright 主题 · 界面截图来自仓库 docs/assets，为历史版本界面，仅用于展示主题配色。"
    },
    dracula: {
      file: "dracula.png",
      shot: "assets/dracula.png",
      color: "#150f1c",
      alt: "SllkGui Dracula 主题界面截图：深紫背景、粉色主按钮与语义色预览。",
      caption: "Dracula 主题 · 界面截图来自仓库 docs/assets，为历史版本界面，仅用于展示主题配色。"
    },
    eye: {
      file: "eye.png",
      shot: "assets/eye.png",
      color: "#0c1713",
      alt: "SllkGui Eye 主题界面截图：墨绿背景、绿色主按钮与语义色预览。",
      caption: "Eye 主题 · 界面截图来自仓库 docs/assets，为历史版本界面，仅用于展示主题配色。"
    }
  };

  var metaTheme = document.querySelector('meta[name="theme-color"]');
  var shotImg = document.getElementById("themeShot");
  var shotFile = document.getElementById("shotFile");
  var shotCaption = document.getElementById("shotCaption");
  var shotToken = 0;

  function readStoredTheme() {
    try {
      return window.localStorage.getItem("sllkgui-portal-theme");
    } catch (error) {
      return null;
    }
  }

  function storeTheme(name) {
    try {
      window.localStorage.setItem("sllkgui-portal-theme", name);
    } catch (error) {
      /* storage may be unavailable; theme still applies for this visit */
    }
  }

  function updateScreenshot(name) {
    var theme = THEMES[name];
    if (!theme || !shotImg) return;

    if (shotFile) shotFile.textContent = theme.file;
    if (shotCaption) shotCaption.textContent = theme.caption;
    if (shotImg.dataset.current === name) return;

    var token = ++shotToken;
    shotImg.classList.add("is-fading");

    var preload = new Image();
    function commit() {
      if (token !== shotToken) return;
      shotImg.src = theme.shot;
      shotImg.alt = theme.alt;
      shotImg.dataset.current = name;
      window.requestAnimationFrame(function () {
        shotImg.classList.remove("is-fading");
      });
    }
    preload.onload = commit;
    preload.onerror = commit;
    preload.src = theme.shot;
  }

  function applyTheme(name, persist) {
    var theme = THEMES[name];
    if (!theme) return;

    root.setAttribute("data-theme", name);

    document.querySelectorAll("[data-set-theme]").forEach(function (button) {
      button.setAttribute("aria-pressed", String(button.dataset.setTheme === name));
    });

    document.querySelectorAll("[data-theme-target]").forEach(function (tab) {
      var active = tab.dataset.themeTarget === name;
      tab.classList.toggle("is-active", active);
      tab.setAttribute("aria-selected", String(active));
      tab.tabIndex = active ? 0 : -1;
    });

    if (metaTheme) metaTheme.setAttribute("content", theme.color);
    updateScreenshot(name);
    if (persist) storeTheme(name);
  }

  document.querySelectorAll("[data-set-theme]").forEach(function (button) {
    button.addEventListener("click", function () {
      applyTheme(button.dataset.setTheme, true);
    });
  });

  var themeTabs = Array.prototype.slice.call(document.querySelectorAll("[data-theme-target]"));
  themeTabs.forEach(function (tab, index) {
    tab.addEventListener("click", function () {
      applyTheme(tab.dataset.themeTarget, true);
    });
    tab.addEventListener("keydown", function (event) {
      var next = null;
      if (event.key === "ArrowRight" || event.key === "ArrowDown") next = (index + 1) % themeTabs.length;
      if (event.key === "ArrowLeft" || event.key === "ArrowUp") next = (index - 1 + themeTabs.length) % themeTabs.length;
      if (event.key === "Home") next = 0;
      if (event.key === "End") next = themeTabs.length - 1;
      if (next === null) return;
      event.preventDefault();
      themeTabs[next].focus();
      themeTabs[next].click();
    });
  });

  var initialTheme = readStoredTheme();
  applyTheme(THEMES[initialTheme] ? initialTheme : "default", false);

  /* ------------------------------------------------------------------
     Header state, mobile menu, scroll spy
     ------------------------------------------------------------------ */
  var header = document.getElementById("siteHeader");
  var navToggle = document.querySelector(".nav-toggle");
  var mobileMenu = document.getElementById("mobileMenu");
  var desktopQuery = window.matchMedia("(min-width: 1025px)");
  var navLinks = Array.prototype.slice.call(document.querySelectorAll("[data-nav]"));
  var sections = navLinks
    .map(function (link) { return document.getElementById(link.dataset.nav); })
    .filter(Boolean);

  function closeMenu() {
    if (!mobileMenu || !navToggle) return;
    mobileMenu.hidden = true;
    navToggle.classList.remove("is-open");
    navToggle.setAttribute("aria-expanded", "false");
    navToggle.setAttribute("aria-label", "打开菜单");
  }

  if (navToggle && mobileMenu) {
    navToggle.addEventListener("click", function () {
      var open = mobileMenu.hidden;
      mobileMenu.hidden = !open;
      navToggle.classList.toggle("is-open", open);
      navToggle.setAttribute("aria-expanded", String(open));
      navToggle.setAttribute("aria-label", open ? "关闭菜单" : "打开菜单");
    });

    mobileMenu.querySelectorAll("a").forEach(function (link) {
      link.addEventListener("click", closeMenu);
    });

    document.addEventListener("keydown", function (event) {
      if (event.key === "Escape" && !mobileMenu.hidden) {
        closeMenu();
        navToggle.focus();
      }
    });

    var onViewportChange = function (event) {
      if (event.matches) closeMenu();
    };
    if (desktopQuery.addEventListener) {
      desktopQuery.addEventListener("change", onViewportChange);
    } else if (desktopQuery.addListener) {
      desktopQuery.addListener(onViewportChange);
    }
  }

  function updateActiveSection() {
    if (!sections.length) return;
    var marker = window.scrollY + (header ? header.offsetHeight : 0) + 120;
    var current = sections[0];
    for (var i = 0; i < sections.length; i += 1) {
      if (sections[i].getBoundingClientRect().top + window.scrollY <= marker) {
        current = sections[i];
      }
    }
    var atBottom = window.innerHeight + window.scrollY >= document.documentElement.scrollHeight - 4;
    if (atBottom) current = sections[sections.length - 1];

    navLinks.forEach(function (link) {
      link.classList.toggle("is-active", link.dataset.nav === current.id);
    });
  }

  var scrollTicking = false;
  function onScroll() {
    if (scrollTicking) return;
    scrollTicking = true;
    window.requestAnimationFrame(function () {
      if (header) header.classList.toggle("is-scrolled", window.scrollY > 10);
      updateActiveSection();
      scrollTicking = false;
    });
  }
  window.addEventListener("scroll", onScroll, { passive: true });
  onScroll();

  /* ------------------------------------------------------------------
     Scroll reveal
     ------------------------------------------------------------------ */
  var revealItems = document.querySelectorAll(".reveal-on-scroll");
  if ("IntersectionObserver" in window && !prefersReduced) {
    var revealObserver = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (entry.isIntersecting) {
          entry.target.classList.add("is-visible");
          revealObserver.unobserve(entry.target);
        }
      });
    }, { threshold: 0.12, rootMargin: "0px 0px -6% 0px" });
    revealItems.forEach(function (item) { revealObserver.observe(item); });
  } else {
    revealItems.forEach(function (item) { item.classList.add("is-visible"); });
  }

  /* ------------------------------------------------------------------
     Copy buttons
     ------------------------------------------------------------------ */
  document.querySelectorAll("[data-copy-target]").forEach(function (button) {
    button.addEventListener("click", function () {
      var target = document.getElementById(button.dataset.copyTarget);
      if (!target) return;
      var text = target.innerText;

      function done() {
        window.clearTimeout(button._copyTimer);
        button.textContent = "已复制";
        button.classList.add("is-copied");
        button._copyTimer = window.setTimeout(function () {
          button.textContent = "复制";
          button.classList.remove("is-copied");
        }, 1600);
      }

      function fallbackCopy() {
        var area = document.createElement("textarea");
        area.value = text;
        area.setAttribute("readonly", "");
        area.style.position = "fixed";
        area.style.opacity = "0";
        document.body.appendChild(area);
        area.select();
        try {
          document.execCommand("copy");
          done();
        } catch (error) {
          button.textContent = "复制失败";
        }
        document.body.removeChild(area);
      }

      if (navigator.clipboard && window.isSecureContext) {
        navigator.clipboard.writeText(text).then(done).catch(fallbackCopy);
      } else {
        fallbackCopy();
      }
    });
  });

  /* ------------------------------------------------------------------
     Subtle tilt on the hero window (desktop, fine pointer only)
     ------------------------------------------------------------------ */
  var heroVisual = document.querySelector(".hero-visual");
  var appWindow = document.querySelector(".app-window");
  var tiltQuery = window.matchMedia("(min-width: 1151px) and (pointer: fine)");

  if (heroVisual && appWindow && tiltQuery.matches && !prefersReduced) {
    heroVisual.addEventListener("pointermove", function (event) {
      var rect = heroVisual.getBoundingClientRect();
      var x = (event.clientX - rect.left) / rect.width - 0.5;
      var y = (event.clientY - rect.top) / rect.height - 0.5;
      appWindow.classList.add("is-tilting");
      appWindow.style.transform =
        "rotateY(" + (-3 + x * 5).toFixed(2) + "deg) rotateX(" + (1.5 - y * 4).toFixed(2) + "deg)";
    });
    heroVisual.addEventListener("pointerleave", function () {
      appWindow.classList.remove("is-tilting");
      appWindow.style.transform = "";
    });
    window.addEventListener("resize", function () {
      if (window.matchMedia("(min-width: 1151px) and (pointer: fine)").matches) return;
      appWindow.classList.remove("is-tilting");
      appWindow.style.transform = "";
    });
  }
})();
