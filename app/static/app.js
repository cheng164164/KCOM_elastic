document.addEventListener("DOMContentLoaded", function () {
    const form = document.getElementById("question-form");
    const submitBtn = document.querySelector(".submit-btn");

    if (form && submitBtn) {
        form.addEventListener("submit", function () {
            submitBtn.disabled = true;
            submitBtn.textContent = "Submitting...";
        });
    }
});