document.addEventListener("DOMContentLoaded", () => {
  const cards = document.querySelectorAll(".reveal-card");
  if (cards.length === 0) {
    return;
  }

  const reveal = (card, delay = 0) => {
    window.setTimeout(() => card.classList.add("is-visible"), delay);
  };

  if (!("IntersectionObserver" in window)) {
    cards.forEach((card, index) => reveal(card, index * 40));
    return;
  }

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
});
