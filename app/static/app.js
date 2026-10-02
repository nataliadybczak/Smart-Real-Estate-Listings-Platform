// Filters: changing a select / checkbox refreshes results immediately
// (number inputs submit on Enter or via the button).
document.querySelectorAll("[data-autosubmit]").forEach((element) => {
  element.addEventListener("change", () => {
    const pageField = element.form.querySelector("input[name=page]");
    if (pageField) pageField.remove(); // new filters = back to page 1
    element.form.requestSubmit();
  });
});

// Do not send empty fields, so the URL stays short and readable.
const filtersForm = document.getElementById("filters");
if (filtersForm) {
  filtersForm.addEventListener("formdata", (event) => {
    for (const [key, value] of [...event.formData.entries()]) {
      if (value === "") event.formData.delete(key);
    }
  });
}

// Photo carousels (listing cards and the listing gallery): swipe / scroll, arrows,
// optional thumbnails and - on the listing page - keyboard arrows.
function initCarousel(root) {
  const track = root.querySelector(".carousel__track");
  const slides = track.children;
  const counter = root.querySelector(".carousel__counter");
  const thumbs = root.querySelectorAll(".gallery__thumb");
  const currentIndex = () => Math.round(track.scrollLeft / track.clientWidth);
  const goTo = (index) => {
    const target = Math.max(0, Math.min(slides.length - 1, index));
    track.scrollTo({ left: target * track.clientWidth, behavior: "smooth" });
  };

  root.querySelectorAll("[data-step]").forEach((button) => {
    button.addEventListener("click", (event) => {
      event.preventDefault(); // arrows on a card must not open the listing
      goTo(currentIndex() + Number(button.dataset.step));
    });
  });
  thumbs.forEach((thumb) => thumb.addEventListener("click", () => goTo(Number(thumb.dataset.index))));
  if (root.hasAttribute("data-keyboard")) {
    document.addEventListener("keydown", (event) => {
      if (event.key === "ArrowLeft") goTo(currentIndex() - 1);
      if (event.key === "ArrowRight") goTo(currentIndex() + 1);
    });
  }

  // Keep the counter and the highlighted thumbnail in sync with the visible photo.
  track.addEventListener("scroll", () => {
    const index = currentIndex();
    if (counter) counter.textContent = `${index + 1} / ${slides.length}`;
    thumbs.forEach((thumb, i) => thumb.classList.toggle("is-active", i === index));
    thumbs[index]?.scrollIntoView({ block: "nearest", inline: "nearest" });
  }, { passive: true });
}

document.querySelectorAll("[data-carousel]").forEach((root) => {
  if (root.querySelector(".carousel__track")) initCarousel(root);
});

// Compare page: hide rows where all listings have the same value.
document.querySelectorAll("[data-only-differences]").forEach((toggle) => {
  toggle.addEventListener("change", () => {
    document.getElementById("compare").classList.toggle("only-differences", toggle.checked);
  });
});
