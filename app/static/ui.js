document.addEventListener("DOMContentLoaded", () => {
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
});
