document.addEventListener("DOMContentLoaded", () => {
  const appShell = document.getElementById("appShell");
  const sidebar = document.getElementById("siteSidebar");
  const backdrop = document.getElementById("sidebarBackdrop");
  const openButtons = [document.getElementById("mobileTopbarMenu")].filter(Boolean);

  const setNavOpen = (open) => {
    if (!appShell || !sidebar || !backdrop) return;
    appShell.classList.toggle("is-nav-open", open);
    backdrop.hidden = !open;
    openButtons.forEach((btn) => btn.setAttribute("aria-expanded", open ? "true" : "false"));
    document.body.style.overflow = open ? "hidden" : "";
  };

  openButtons.forEach((btn) => {
    btn.addEventListener("click", () => {
      setNavOpen(!appShell?.classList.contains("is-nav-open"));
    });
  });

  backdrop?.addEventListener("click", () => setNavOpen(false));

  sidebar?.querySelectorAll(".nav-link, .logout-link").forEach((link) => {
    link.addEventListener("click", () => setNavOpen(false));
  });

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") setNavOpen(false);
  });

  window.addEventListener("resize", () => {
    if (window.innerWidth > 768) setNavOpen(false);
  });

  const cards = document.querySelectorAll(".reveal-card");
  if (cards.length > 0) {
    const reveal = (card, delay = 0) => {
      window.setTimeout(() => card.classList.add("is-visible"), delay);
    };

    if (!("IntersectionObserver" in window)) {
      cards.forEach((card, index) => reveal(card, index * 40));
    } else {
      const observer = new IntersectionObserver(
        (entries) => {
          entries.forEach((entry) => {
            if (entry.isIntersecting) {
              reveal(entry.target);
              observer.unobserve(entry.target);
            }
          });
        },
        { threshold: 0.12, rootMargin: "0px 0px -40px 0px" }
      );
      cards.forEach((card) => observer.observe(card));
    }
  }

  const catalogSort = document.getElementById("catalogSort");
  const catalogForm = document.getElementById("catalogForm");
  if (catalogSort && catalogForm) {
    catalogSort.addEventListener("change", () => catalogForm.submit());
  }

  document.querySelectorAll(".file-input input[type='file']").forEach((input) => {
    const nameEl = input.closest(".file-input")?.querySelector(".file-input-name");
    const fallback = input.dataset.fileLabel || "Файл не выбран";
    input.addEventListener("change", () => {
      if (!nameEl) return;
      nameEl.textContent = input.files?.[0]?.name || fallback;
    });
  });

  if (window.location.hash === "#comments") {
    const comments = document.getElementById("comments");
    if (comments) {
      window.setTimeout(() => comments.scrollIntoView({ behavior: "smooth", block: "start" }), 120);
    }
  }

  const backBtn = document.getElementById("backBtn");
  if (backBtn) {
    backBtn.addEventListener("click", () => {
      if (window.history.length > 1) {
        window.history.back();
      } else {
        window.location.href = "/";
      }
    });
  }

  document.querySelectorAll("[data-action-menu]").forEach((menuRoot) => {
    const toggle = menuRoot.querySelector(".action-menu-toggle");
    const panel = menuRoot.querySelector(".action-menu-panel");
    if (!toggle || !panel) return;

    const closeMenu = () => {
      panel.hidden = true;
      toggle.setAttribute("aria-expanded", "false");
    };

    toggle.addEventListener("click", (event) => {
      event.stopPropagation();
      const willOpen = panel.hidden;
      document.querySelectorAll(".action-menu-panel").forEach((other) => {
        other.hidden = true;
      });
      document.querySelectorAll(".action-menu-toggle").forEach((otherToggle) => {
        otherToggle.setAttribute("aria-expanded", "false");
      });
      panel.hidden = !willOpen;
      toggle.setAttribute("aria-expanded", willOpen ? "true" : "false");
    });

    document.addEventListener("click", (event) => {
      if (!menuRoot.contains(event.target)) {
        closeMenu();
      }
    });

    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape") {
        closeMenu();
      }
    });
  });
});
