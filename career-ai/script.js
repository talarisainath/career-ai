/*
 * script.js
 * UI behaviour for CareerAI: navigation, the multi-step assessment,
 * result rendering, career directory, and the detail modal.
 *
 * Recommendations and catalog data come from the Python API
 * (backend/app/main.py). The bundled JavaScript engine is used only for an
 * explicit offline demo mode and for backend parity tests.
 */
(function () {
  "use strict";

  const AI = window.CareerAI;

  /* ------------------------------------------------------------------ *
   * Small helpers
   * ------------------------------------------------------------------ */

  function byId(id) { return document.getElementById(id); }

  function escapeHTML(value) {
    return String(value).replace(/[&<>"']/g, function (ch) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", "\"": "&quot;", "'": "&#39;" }[ch];
    });
  }

  let toastTimer = null;
  function toast(message) {
    const el = byId("toast");
    el.textContent = message;
    el.hidden = false;
    el.classList.add("is-visible");
    clearTimeout(toastTimer);
    toastTimer = setTimeout(function () {
      el.classList.remove("is-visible");
      setTimeout(function () { el.hidden = true; }, 250);
    }, 3200);
  }

  /* ------------------------------------------------------------------ *
   * API client — the Python backend is the authoritative engine
   * ------------------------------------------------------------------ */

  /*
   * Production uses the page's own origin, so requests are simply
   * `/api/...`. When the frontend is served separately on the local
   * development port (run-frontend.bat), point at the local API on 8000.
   * `window.CAREERAI_API_BASE` can override either behaviour.
   */
  function resolveApiBase() {
    if (typeof window.CAREERAI_API_BASE === "string") {
      return window.CAREERAI_API_BASE.trim().replace(/\/+$/, "");
    }
    if (window.location.protocol === "file:") {
      return "http://127.0.0.1:8000";
    }
    const localHost = window.location.hostname === "127.0.0.1" ||
      window.location.hostname === "localhost" ||
      window.location.hostname === "[::1]";
    if (localHost && window.location.port === "5500") {
      return window.location.protocol + "//" + window.location.hostname + ":8000";
    }
    return "";
  }

  const API_BASE = resolveApiBase();
  const API_TIMEOUT_MS = 15000;
  let apiBannerTimer = null;

  function apiTargetLabel() {
    if (API_BASE) return API_BASE;
    if (window.location.origin && window.location.origin !== "null") {
      return window.location.origin;
    }
    return "the CareerAI service";
  }

  const LOCAL_BACKEND_HINT = API_BASE
    ? " Start the backend with run-backend.bat, then retry."
    : " Please refresh the page or try again in a moment.";

  function apiFetch(path, options) {
    const controller = typeof AbortController === "function" ? new AbortController() : null;
    const timer = controller
      ? setTimeout(function () { controller.abort(); }, API_TIMEOUT_MS)
      : null;
    const init = Object.assign({}, options || {});
    if (controller) init.signal = controller.signal;
    return fetch(API_BASE + path, init).finally(function () {
      if (timer) clearTimeout(timer);
    });
  }

  function setApiBanner(kind, message, options) {
    const banner = byId("api-banner");
    const retry = byId("api-banner-retry");
    clearTimeout(apiBannerTimer);

    if (!message) {
      banner.hidden = true;
      return;
    }

    banner.hidden = false;
    banner.classList.remove("is-loading", "is-online", "is-offline");
    banner.classList.add("is-" + kind);
    banner.setAttribute("role", kind === "offline" ? "alert" : "status");
    byId("api-banner-text").textContent = message;
    retry.hidden = kind !== "offline";

    if (options && options.autoHide) {
      apiBannerTimer = setTimeout(function () { banner.hidden = true; }, 4500);
    }
  }

  async function readErrorDetail(response) {
    try {
      const body = await response.json();
      if (body && Array.isArray(body.detail)) {
        return body.detail.map(function (item) {
          return item && item.msg ? item.msg : String(item);
        }).join(" ");
      }
      if (body && typeof body.detail === "string") return body.detail;
    } catch (error) {
      /* Response was not JSON. */
    }
    return "The service returned HTTP " + response.status + ".";
  }

  function apiUnavailableMessage(error) {
    if (error && error.name === "AbortError") {
      return "The CareerAI service at " + apiTargetLabel() + " took too long to respond." +
        LOCAL_BACKEND_HINT;
    }
    return "Could not reach the CareerAI service at " + apiTargetLabel() + "." +
      LOCAL_BACKEND_HINT;
  }

  async function requestRecommendations(profile) {
    let response;
    try {
      response = await apiFetch("/api/recommendations", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(profile)
      });
    } catch (error) {
      state.api.online = false;
      throw new Error(apiUnavailableMessage(error));
    }

    if (response.status === 422) {
      const detail = await readErrorDetail(response);
      const error = new Error(
        "The assessment was rejected by the service: " + detail +
        " Check your answers and try again."
      );
      error.isValidation = true;
      throw error;
    }
    if (!response.ok) {
      throw new Error(
        "The recommendation service ran into a problem (HTTP " +
        response.status + "). Please retry."
      );
    }

    state.api.online = true;
    return response.json();
  }

  /* Explicit demo mode: only runs after the user chooses it. */
  function demoRecommendations(profile) {
    return new Promise(function (resolve, reject) {
      setTimeout(function () {
        try {
          const result = AI.RecommendationEngine.computeMatches(profile, AI.careers);
          result.source = "local-demo";
          resolve(result);
        } catch (error) {
          reject(error);
        }
      }, 400);
    });
  }

  function setBusy(busy) {
    ["btn-generate", "btn-retry-recommendations", "btn-demo-mode"].forEach(function (id) {
      const element = byId(id);
      if (element) element.disabled = busy;
    });
    const section = byId("results");
    if (section) section.setAttribute("aria-busy", busy ? "true" : "false");
  }

  async function loadCatalog() {
    setApiBanner("loading", "Connecting to the CareerAI service…");
    try {
      const response = await apiFetch("/api/careers");
      if (!response.ok) throw new Error("HTTP " + response.status);
      const data = await response.json();
      if (!Array.isArray(data.careers) || data.careers.length === 0) {
        throw new Error("The service returned an empty catalog.");
      }

      AI.careers = data.careers;
      state.api.online = true;
      initCounts();
      Explore.renderChips();
      Explore.render();
      setApiBanner(
        "online",
        "Career service connected — " + data.careers.length + " careers loaded from the API.",
        { autoHide: true }
      );
    } catch (error) {
      state.api.online = false;
      setApiBanner(
        "offline",
        "Backend not connected. You can still browse the bundled demo catalog, " +
        "but recommendations need the API at " + apiTargetLabel() + "." +
        LOCAL_BACKEND_HINT
      );
    }
  }

  /* ------------------------------------------------------------------ *
   * State (kept in memory only — nothing is stored or uploaded)
   * ------------------------------------------------------------------ */

  const TOTAL_STEPS = 5;
  const STEP_NAMES = ["About you", "Skills", "Interests", "Academics", "Preferences"];

  const state = {
    step: 1,
    profile: {
      name: "", education: "", branch: "", percent: null, country: "",
      skills: {}, interests: [], subjects: {}, workStyles: []
    },
    lastResult: null,
    showAllResults: false,
    api: { online: false, submitting: false, demoMode: false, requestId: 0 }
  };

  function emptyProfile() {
    return {
      name: "", education: "", branch: "", percent: null, country: "",
      skills: {}, interests: [], subjects: {}, workStyles: []
    };
  }

  function hasProfileData() {
    const p = state.profile;
    return p.education !== "" || p.branch !== "" ||
      Object.keys(p.skills).length > 0 || p.interests.length > 0 ||
      Object.keys(p.subjects).length > 0 || p.workStyles.length > 0;
  }

  /* ------------------------------------------------------------------ *
   * Navigation
   * ------------------------------------------------------------------ */

  function initNav() {
    const header = byId("site-header");
    const toggle = byId("nav-toggle");
    const menu = byId("primary-menu");

    function setMenu(open) {
      menu.classList.toggle("is-open", open);
      toggle.setAttribute("aria-expanded", String(open));
      toggle.setAttribute("aria-label", open ? "Close navigation menu" : "Open navigation menu");
      document.body.classList.toggle("menu-open", open);
    }

    toggle.addEventListener("click", function () {
      setMenu(!menu.classList.contains("is-open"));
    });

    menu.querySelectorAll("a").forEach(function (link) {
      link.addEventListener("click", function () { setMenu(false); });
    });

    document.addEventListener("keydown", function (event) {
      if (event.key === "Escape" && menu.classList.contains("is-open")) {
        setMenu(false);
        toggle.focus();
      }
    });

    window.addEventListener("resize", function () {
      if (window.innerWidth > 860) setMenu(false);
    });

    window.addEventListener("scroll", function () {
      header.classList.toggle("is-scrolled", window.scrollY > 8);
    }, { passive: true });

    /* Highlight the section currently in view. */
    const navLinks = Array.prototype.slice.call(menu.querySelectorAll(".nav-link"));
    if ("IntersectionObserver" in window) {
      const observer = new IntersectionObserver(function (entries) {
        entries.forEach(function (entry) {
          if (!entry.isIntersecting) return;
          navLinks.forEach(function (link) {
            link.classList.toggle("is-active",
              link.getAttribute("href") === "#" + entry.target.id);
          });
        });
      }, { rootMargin: "-35% 0px -55% 0px" });

      ["home", "assessment", "explore", "about"].forEach(function (id) {
        const section = byId(id);
        if (section) observer.observe(section);
      });
    }
  }

  /* ------------------------------------------------------------------ *
   * Dynamic counts (always reflect the real dataset)
   * ------------------------------------------------------------------ */

  function initCounts() {
    const careers = AI.careers;
    const categories = [];
    careers.forEach(function (career) {
      if (categories.indexOf(career.category) === -1) categories.push(career.category);
    });

    byId("stat-careers").textContent = String(careers.length);
    byId("stat-categories").textContent = String(categories.length);
    byId("explore-count").textContent = String(careers.length);
    byId("footer-year").textContent = String(new Date().getFullYear());

    const footerList = byId("footer-categories");
    footerList.innerHTML = "";
    categories.forEach(function (category) {
      const li = document.createElement("li");
      const link = document.createElement("a");
      link.href = "#explore";
      link.textContent = category;
      link.addEventListener("click", function () {
        Explore.filterByCategory(category);
      });
      li.appendChild(link);
      footerList.appendChild(li);
    });
  }

  /* ------------------------------------------------------------------ *
   * Assessment — building the option controls
   * ------------------------------------------------------------------ */

  function buildSelects() {
    const edu = byId("f-education");
    AI.EDUCATION_LEVELS.forEach(function (item) {
      const option = document.createElement("option");
      option.value = item.value;
      option.textContent = item.label;
      edu.appendChild(option);
    });

    const branch = byId("f-branch");
    AI.BRANCHES.forEach(function (item) {
      const option = document.createElement("option");
      option.value = item.value;
      option.textContent = item.label;
      branch.appendChild(option);
    });
  }

  function buildSkillsGrid() {
    const grid = byId("skills-grid");
    AI.SKILL_ORDER.forEach(function (key) {
      const card = document.createElement("div");
      card.className = "option-card skill-card";

      const label = document.createElement("label");
      label.className = "option-main";
      label.innerHTML =
        '<input type="checkbox" class="option-input" data-skill="' + key + '">' +
        '<span class="option-name">' + escapeHTML(AI.SKILL_LABELS[key]) + "</span>";

      const rating = document.createElement("div");
      rating.className = "rating";
      rating.setAttribute("role", "group");
      rating.setAttribute("aria-label", "Proficiency for " + AI.SKILL_LABELS[key]);
      rating.hidden = true;

      for (let level = 1; level <= 5; level++) {
        const rateId = "rate-" + key + "-" + level;
        const rateLabel = document.createElement("label");
        rateLabel.className = "rating-dot";
        rateLabel.setAttribute("for", rateId);
        rateLabel.textContent = String(level);
        const radio = document.createElement("input");
        radio.type = "radio";
        radio.name = "prof-" + key;
        radio.id = rateId;
        radio.value = String(level);
        radio.className = "visually-hidden";
        radio.addEventListener("change", function () {
          state.profile.skills[key] = level;
        });
        rateLabel.insertBefore(radio, rateLabel.firstChild);
        rating.appendChild(rateLabel);
      }

      const hint = document.createElement("span");
      hint.className = "rating-hint";
      hint.textContent = "Proficiency 1–5";
      hint.hidden = true;

      card.appendChild(label);
      card.appendChild(rating);
      card.appendChild(hint);

      label.querySelector("input").addEventListener("change", function (event) {
        if (event.target.checked) {
          state.profile.skills[key] = state.profile.skills[key] || 3;
          rating.hidden = false;
          hint.hidden = false;
          card.classList.add("is-selected");
        } else {
          delete state.profile.skills[key];
          rating.hidden = true;
          hint.hidden = true;
          card.classList.remove("is-selected");
          const checked = rating.querySelector("input:checked");
          if (checked) checked.checked = false;
        }
      });

      grid.appendChild(card);
    });
  }

  function buildCheckboxGrid(containerId, order, labels, group) {
    const container = byId(containerId);
    order.forEach(function (key) {
      const card = document.createElement("label");
      card.className = "option-card select-card";
      card.innerHTML =
        '<input type="checkbox" class="option-input">' +
        '<span class="option-name">' + escapeHTML(labels[key]) + "</span>" +
        '<span class="option-tick" aria-hidden="true"></span>';

      card.querySelector("input").addEventListener("change", function (event) {
        const list = state.profile[group];
        const index = list.indexOf(key);
        if (event.target.checked) {
          if (index === -1) list.push(key);
          card.classList.add("is-selected");
        } else {
          if (index !== -1) list.splice(index, 1);
          card.classList.remove("is-selected");
        }
      });

      container.appendChild(card);
    });
  }

  function buildSubjects() {
    const list = byId("subjects-list");
    AI.SUBJECT_ORDER.forEach(function (key) {
      const row = document.createElement("div");
      row.className = "subject-row";

      const toggleId = "subj-toggle-" + key;
      const sliderId = "subj-slider-" + key;

      const toggle = document.createElement("input");
      toggle.type = "checkbox";
      toggle.className = "subject-include";
      toggle.id = toggleId;

      const label = document.createElement("label");
      label.className = "subject-name";
      label.setAttribute("for", toggleId);
      label.textContent = AI.SUBJECT_LABELS[key];

      const slider = document.createElement("input");
      slider.type = "range";
      slider.min = "0";
      slider.max = "100";
      slider.step = "1";
      slider.value = "75";
      slider.id = sliderId;
      slider.disabled = true;
      slider.setAttribute("aria-label", AI.SUBJECT_LABELS[key] + " mark out of 100");

      const output = document.createElement("output");
      output.className = "subject-value";
      output.setAttribute("for", sliderId);
      output.textContent = "—";

      toggle.addEventListener("change", function () {
        slider.disabled = !toggle.checked;
        if (toggle.checked) {
          state.profile.subjects[key] = Number(slider.value);
          output.textContent = slider.value + "%";
        } else {
          delete state.profile.subjects[key];
          output.textContent = "—";
        }
      });

      slider.addEventListener("input", function () {
        output.textContent = slider.value + "%";
        if (toggle.checked) state.profile.subjects[key] = Number(slider.value);
      });

      row.appendChild(toggle);
      row.appendChild(label);
      row.appendChild(slider);
      row.appendChild(output);
      list.appendChild(row);
    });
  }

  /* ------------------------------------------------------------------ *
   * Assessment — steps, validation, navigation
   * ------------------------------------------------------------------ */

  function showAlert(message, target) {
    const alert = byId("form-alert");
    alert.textContent = message;
    alert.hidden = false;
    alert.classList.add("is-shaking");
    setTimeout(function () { alert.classList.remove("is-shaking"); }, 400);
    if (target) target.focus();
  }

  function clearAlert() {
    const alert = byId("form-alert");
    alert.hidden = true;
    alert.textContent = "";
  }

  function readPersonalFields() {
    const p = state.profile;
    p.name = byId("f-name").value.trim();
    p.education = byId("f-education").value;
    p.branch = byId("f-branch").value;
    const percentRaw = byId("f-percent").value.trim();
    p.percent = percentRaw === "" ? null : Number(percentRaw);
    p.country = byId("f-country").value.trim();
  }

  function validateStep(step) {
    if (step === 1) {
      readPersonalFields();
      const p = state.profile;
      if (!p.education) {
        return { ok: false, message: "Please select your education level to continue.", target: byId("f-education") };
      }
      if (!p.branch) {
        return { ok: false, message: "Please select your academic branch or stream.", target: byId("f-branch") };
      }
      if (p.percent !== null && (!isFinite(p.percent) || p.percent < 0 || p.percent > 100)) {
        return { ok: false, message: "Overall percentage must be a number between 0 and 100 (or left blank).", target: byId("f-percent") };
      }
      return { ok: true };
    }
    if (step === 2) {
      const count = Object.keys(state.profile.skills).length;
      if (count < 3) {
        return { ok: false, message: "Select at least 3 skills — you have chosen " + count + " so far." };
      }
      return { ok: true };
    }
    if (step === 3) {
      if (state.profile.interests.length < 2) {
        return { ok: false, message: "Select at least 2 interests so matching has something to work with." };
      }
      return { ok: true };
    }
    return { ok: true }; /* steps 4 and 5: step 4 optional, step 5 checked on submit */
  }

  function updateProgress() {
    const step = state.step;
    document.querySelectorAll(".step-dot").forEach(function (dot) {
      const dotStep = Number(dot.getAttribute("data-step-dot"));
      dot.classList.toggle("is-active", dotStep === step);
      dot.classList.toggle("is-done", dotStep < step);
      if (dotStep === step) dot.setAttribute("aria-current", "step");
      else dot.removeAttribute("aria-current");
    });

    const bar = byId("progress-bar");
    bar.setAttribute("aria-valuenow", String(step));
    byId("progress-fill").style.width = (step / TOTAL_STEPS) * 100 + "%";
    byId("progress-text").textContent = "Step " + step + " of " + TOTAL_STEPS + " — " + STEP_NAMES[step - 1];
  }

  function updateReviewBox() {
    const p = state.profile;
    const list = byId("review-list");
    const rows = [
      ["Profile", [p.education ? educationLabel(p.education) : "not set",
                   p.branch ? branchLabel(p.branch) : "not set"].join(" · ")],
      ["Skills selected", String(Object.keys(p.skills).length)],
      ["Interests selected", String(p.interests.length)],
      ["Subjects recorded", String(Object.keys(p.subjects).length)],
      ["Work styles selected", String(p.workStyles.length)]
    ];
    list.innerHTML = "";
    rows.forEach(function (row) {
      const li = document.createElement("li");
      const strong = document.createElement("strong");
      strong.textContent = row[0] + ": ";
      li.appendChild(strong);
      li.appendChild(document.createTextNode(row[1]));
      list.appendChild(li);
    });
  }

  function educationLabel(value) {
    const found = AI.EDUCATION_LEVELS.filter(function (e) { return e.value === value; })[0];
    return found ? found.label : value;
  }

  function branchLabel(value) {
    const found = AI.BRANCHES.filter(function (b) { return b.value === value; })[0];
    return found ? found.label : value;
  }

  function showStep(step, options) {
    state.step = Math.min(TOTAL_STEPS, Math.max(1, step));
    clearAlert();

    document.querySelectorAll(".form-step").forEach(function (fieldset) {
      const active = Number(fieldset.getAttribute("data-step")) === state.step;
      fieldset.hidden = !active;
      fieldset.classList.toggle("is-active", active);
    });

    byId("btn-back").hidden = state.step === 1;
    byId("btn-next").hidden = state.step === TOTAL_STEPS;
    byId("btn-generate").hidden = state.step !== TOTAL_STEPS;

    if (state.step === TOTAL_STEPS) updateReviewBox();
    updateProgress();

    if (options && options.focus) {
      const active = document.querySelector('.form-step[data-step="' + state.step + '"]');
      if (active) active.focus();
    }
    if (options && options.scroll) {
      byId("assessment").scrollIntoView({ behavior: "smooth", block: "start" });
    }
  }

  function initAssessmentNav() {
    byId("btn-next").addEventListener("click", function () {
      const result = validateStep(state.step);
      if (!result.ok) {
        showAlert(result.message, result.target);
        return;
      }
      showStep(state.step + 1, { focus: true });
    });

    byId("btn-back").addEventListener("click", function () {
      if (state.step === 1) return;
      readPersonalFields(); /* preserve what was typed */
      showStep(state.step - 1, { focus: true });
    });

    byId("assessment-form").addEventListener("submit", function (event) {
      event.preventDefault();
      Results.generate();
    });

    byId("btn-restart").addEventListener("click", function () {
      Results.restart(true);
    });
  }

  /* ------------------------------------------------------------------ *
   * Results
   * ------------------------------------------------------------------ */

  const Results = {
    generate: async function () {
      if (state.api.submitting) return; /* prevent duplicate submissions */

      /* Validate every completed step before generating. */
      for (let step = 1; step <= 3; step++) {
        const check = validateStep(step);
        if (!check.ok) {
          showStep(step, { focus: false });
          showAlert(check.message, check.target);
          byId("assessment").scrollIntoView({ behavior: "smooth", block: "start" });
          return;
        }
      }
      if (state.profile.workStyles.length < 1) {
        showStep(5, { focus: false });
        showAlert("Select at least one preferred work style before generating recommendations.");
        return;
      }

      clearAlert(); /* validation passed — drop any earlier message */
      const section = byId("results");
      section.hidden = false;
      byId("results-content").hidden = true;
      byId("results-empty").hidden = true;
      byId("results-error").hidden = true;
      byId("results-source").hidden = true;
      byId("processing-state").hidden = false;
      byId("results-title").textContent = state.api.demoMode
        ? "Running the local demo engine…"
        : "Calculating your matches…";
      byId("results-subtitle").innerHTML = state.api.demoMode
        ? "Demo mode uses the bundled rule engine in your browser. Results may differ from the backend."
        : "Contacting the recommendation service and comparing your profile with the career catalog.";
      section.scrollIntoView({ behavior: "smooth", block: "start" });

      const messages = state.api.demoMode
        ? [
            "Running the bundled rule engine…",
            "Scoring skills and interests…",
            "Balancing academic and work-style signals…",
            "Ranking the closest matches…"
          ]
        : [
            "Contacting the recommendation service…",
            "Scoring skills and interests…",
            "Balancing academic and work-style signals…",
            "Ranking the closest matches…"
          ];
      let msgIndex = 0;
      const ticker = setInterval(function () {
        msgIndex = (msgIndex + 1) % messages.length;
        byId("processing-text").textContent = messages[msgIndex];
      }, 700);

      const requestId = ++state.api.requestId;
      const startedAt = Date.now();
      state.api.submitting = true;
      setBusy(true);

      try {
        const result = state.api.demoMode
          ? await demoRecommendations(Object.assign({}, state.profile))
          : await requestRecommendations(state.profile);

        await Results.waitAtLeast(startedAt, 700);
        if (requestId !== state.api.requestId) return;

        clearInterval(ticker);
        state.lastResult = result;
        state.showAllResults = false;
        Results.render();
        if (!state.api.demoMode) {
          setApiBanner("online", "Career service connected.", { autoHide: true });
        }
      } catch (error) {
        await Results.waitAtLeast(startedAt, 500);
        if (requestId !== state.api.requestId) return;

        clearInterval(ticker);
        const message = state.api.demoMode
          ? "The local demo engine failed: " +
            (error && error.message ? error.message : "unknown error")
          : (error && error.message ? error.message : apiUnavailableMessage(error));
        Results.showError(message, error);
      } finally {
        if (requestId === state.api.requestId) {
          state.api.submitting = false;
          setBusy(false);
        }
      }
    },

    waitAtLeast: function (startedAt, minimum) {
      const remaining = Math.max(0, minimum - (Date.now() - startedAt));
      return new Promise(function (resolve) { setTimeout(resolve, remaining); });
    },

    showError: function (message, error) {
      const validationError = Boolean(error && error.isValidation);
      byId("processing-state").hidden = true;
      byId("results-content").hidden = true;
      byId("results-empty").hidden = true;
      byId("results-error").hidden = false;
      byId("results-error-title").textContent = validationError
        ? "Some answers were rejected"
        : (state.api.demoMode
            ? "The demo engine could not run"
            : "We couldn’t load your recommendations");
      byId("results-error-text").textContent = message;
      byId("btn-demo-mode").hidden = state.api.demoMode || validationError;
      byId("results-title").textContent = "We couldn’t load your recommendations";
      byId("results-subtitle").innerHTML =
        "Your answers are still here in this tab. Retry the service, or explicitly switch to demo mode.";
      byId("results-source").hidden = true;
    },

    render: function () {
      const result = state.lastResult;
      const section = byId("results");
      section.hidden = false;
      byId("processing-state").hidden = true;
      byId("results-error").hidden = true;

      const name = state.profile.name;
      byId("results-title").textContent = name
        ? name + ", here are your career matches"
        : "Here are your career matches";
      byId("results-subtitle").innerHTML =
        "Scores are <strong>indicative profile matches</strong> — how closely each career " +
        "aligns with your answers. They are not probabilities of career success.";

      if (!result || result.status !== "ok") {
        byId("results-content").hidden = true;
        byId("results-empty").hidden = false;
        byId("results-empty-text").textContent =
          (result && result.message) || "There is not enough information to rank careers yet.";
        byId("results-source").hidden = true;
        return;
      }

      byId("results-empty").hidden = true;
      byId("results-content").hidden = false;

      /* Show exactly which engine produced the ranking (never silent demo). */
      const source = byId("results-source");
      source.hidden = false;
      if (result.source === "local-demo") {
        source.innerHTML =
          '<span class="source-tag is-demo">Demo mode — local rule engine</span>' +
          '<button type="button" class="link-btn" id="btn-exit-demo">Connect to the backend instead</button>';
        byId("btn-exit-demo").addEventListener("click", function () {
          state.api.demoMode = false;
          Results.generate();
        });
      } else if (result.source === "python-rule-based") {
        source.innerHTML = '<span class="source-tag">Ranked by the CareerAI API</span>';
      } else {
        source.hidden = true;
      }

      const list = byId("results-list");
      list.innerHTML = "";

      const matches = state.showAllResults ? result.matches : result.matches.slice(0, result.topN);
      matches.forEach(function (match) {
        list.appendChild(Results.buildCard(match));
      });

      const moreBtn = byId("btn-more-results");
      if (result.matches.length > result.topN) {
        moreBtn.hidden = false;
        moreBtn.textContent = state.showAllResults
          ? "Show only the top " + result.topN
          : "Show all " + result.matches.length + " ranked careers";
      } else {
        moreBtn.hidden = true;
      }
    },

    buildCard: function (match) {
      const li = document.createElement("li");
      li.className = "result-card";

      const componentLabels = {
        skills: "Skills",
        interests: "Interests",
        academics: "Academics",
        preferences: "Preferences"
      };

      let componentHTML = "";
      Object.keys(componentLabels).forEach(function (key) {
        const value = match.components[key];
        if (value === null) return;
        componentHTML +=
          '<div class="component-row">' +
            '<span class="component-name">' + componentLabels[key] + "</span>" +
            '<span class="component-track"><span style="width:' + value + '%"></span></span>' +
            '<span class="component-value">' + value + "%</span>" +
          "</div>";
      });

      const skillChips = match.matchedSkills.map(function (key) {
        return '<span class="chip chip-skill">' + escapeHTML(AI.SKILL_LABELS[key] || key) + "</span>";
      }).join("");

      const gapChips = match.skillGaps.map(function (key) {
        return '<span class="chip chip-gap">' + escapeHTML(AI.SKILL_LABELS[key] || key) + "</span>";
      }).join("");

      const reasonItems = match.reasons.map(function (reason) {
        return "<li>" + escapeHTML(reason) + "</li>";
      }).join("");

      li.innerHTML =
        '<div class="result-head">' +
          '<span class="rank-badge" aria-hidden="true">#' + match.rank + "</span>" +
          '<div class="result-heading">' +
            "<h3>" + escapeHTML(match.title) + "</h3>" +
            '<p class="result-cat">' + escapeHTML(match.category) + "</p>" +
          "</div>" +
          '<div class="score-badge" style="--score:' + match.score + '" aria-label="Indicative profile match: ' + match.score + ' out of 100">' +
            "<strong>" + match.score + "</strong><span>match</span>" +
          "</div>" +
        "</div>" +
        '<p class="score-caption">Indicative profile match — not a probability of career success.</p>' +
        '<p class="result-desc">' + escapeHTML(match.shortDescription) + "</p>" +
        '<div class="component-bars">' + componentHTML + "</div>" +
        '<div class="result-block">' +
          "<h4>Why this was recommended</h4>" +
          '<ul class="reason-list">' + reasonItems + "</ul>" +
        "</div>" +
        '<div class="result-block">' +
          "<h4>Skills you already match</h4>" +
          '<div class="chip-row">' + (skillChips || '<span class="chip chip-muted">No overlapping skills recorded</span>') + "</div>" +
        "</div>" +
        '<div class="result-block">' +
          "<h4>Suggested skills to develop</h4>" +
          '<div class="chip-row">' + (gapChips || '<span class="chip chip-muted">Core skills already covered</span>') + "</div>" +
        "</div>" +
        '<div class="result-actions-row">' +
          '<button type="button" class="btn btn-primary" data-open-career="' + escapeHTML(match.id) + '">View Career Details</button>' +
        "</div>";

      li.querySelector("[data-open-career]").addEventListener("click", function () {
        Modal.open(match.id);
      });

      return li;
    },

    restart: function (withConfirm) {
      if (withConfirm && hasProfileData()) {
        const ok = window.confirm("Restart the assessment? Your current answers will be cleared.");
        if (!ok) return;
      }

      byId("assessment-form").reset();
      state.profile = emptyProfile();
      state.lastResult = null;
      state.showAllResults = false;

      document.querySelectorAll(".skill-card").forEach(function (card) {
        card.classList.remove("is-selected");
        const rating = card.querySelector(".rating");
        const hint = card.querySelector(".rating-hint");
        if (rating) rating.hidden = true;
        if (hint) hint.hidden = true;
        const checked = card.querySelector('input[type="radio"]:checked');
        if (checked) checked.checked = false;
      });
      document.querySelectorAll(".select-card").forEach(function (card) {
        card.classList.remove("is-selected");
      });
      document.querySelectorAll(".subject-row").forEach(function (row) {
        const slider = row.querySelector('input[type="range"]');
        const output = row.querySelector("output");
        slider.disabled = true;
        slider.value = "75";
        output.textContent = "—";
      });

      byId("results").hidden = true;
      byId("results-content").hidden = true;
      byId("results-empty").hidden = true;
      byId("results-error").hidden = true;
      byId("results-source").hidden = true;
      byId("processing-state").hidden = true;
      state.api.demoMode = false;
      state.api.requestId += 1;
      state.api.submitting = false;
      setBusy(false);
      showStep(1, { focus: true });
      byId("assessment").scrollIntoView({ behavior: "smooth", block: "start" });
      toast("Assessment restarted — all answers cleared.");
    },

    toggleAll: function () {
      state.showAllResults = !state.showAllResults;
      Results.render();
    }
  };

  /* ------------------------------------------------------------------ *
   * Explore directory
   * ------------------------------------------------------------------ */

  const Explore = {
    query: "",
    category: "All",

    renderChips: function () {
      const container = byId("filter-chips");
      const categories = ["All"];
      AI.careers.forEach(function (career) {
        if (categories.indexOf(career.category) === -1) categories.push(career.category);
      });

      container.innerHTML = "";
      categories.forEach(function (category) {
        const chip = document.createElement("button");
        chip.type = "button";
        chip.className = "chip-btn" + (category === Explore.category ? " is-active" : "");
        chip.textContent = category;
        chip.setAttribute("aria-pressed", String(category === Explore.category));
        chip.addEventListener("click", function () {
          Explore.filterByCategory(category);
        });
        container.appendChild(chip);
      });
    },

    filterByCategory: function (category) {
      Explore.category = category;
      Explore.renderChips();
      Explore.render();
      byId("explore").scrollIntoView({ behavior: "smooth", block: "start" });
    },

    matches: function (career) {
      const q = Explore.query.trim().toLowerCase();
      if (Explore.category !== "All" && career.category !== Explore.category) return false;
      if (!q) return true;

      const haystack = [
        career.title, career.category, career.shortDescription, career.overview
      ].concat(
        career.coreSkills.map(function (s) { return AI.SKILL_LABELS[s] || s; }),
        career.interests.map(function (i) { return AI.INTEREST_LABELS[i] || i; }),
        career.skillsToLearn
      ).join(" ").toLowerCase();

      return haystack.indexOf(q) !== -1;
    },

    render: function () {
      const grid = byId("career-grid");
      const results = AI.careers.filter(Explore.matches);

      grid.innerHTML = "";
      results.forEach(function (career) {
        grid.appendChild(Explore.buildCard(career));
      });

      const empty = results.length === 0;
      byId("explore-empty").hidden = !empty;
      grid.hidden = empty;

      const status = byId("explore-status");
      if (empty) {
        status.textContent = "No careers found.";
      } else {
        status.textContent = results.length + " of " + AI.careers.length + " careers" +
          (Explore.category !== "All" ? " in " + Explore.category : "") +
          (Explore.query.trim() ? ' matching "' + Explore.query.trim() + '"' : "");
      }
    },

    buildCard: function (career) {
      const card = document.createElement("article");
      card.className = "career-card";

      const skillChips = career.coreSkills.slice(0, 4).map(function (key) {
        return '<span class="chip chip-skill">' + escapeHTML(AI.SKILL_LABELS[key] || key) + "</span>";
      }).join("");

      card.innerHTML =
        '<div class="career-card-top">' +
          '<span class="category-tag">' + escapeHTML(career.category) + "</span>" +
          (state.lastResult && state.lastResult.status === "ok"
            ? '<span class="mini-match">' + Results.matchScoreFor(career.id) + " match</span>"
            : "") +
        "</div>" +
        "<h3>" + escapeHTML(career.title) + "</h3>" +
        '<p class="career-card-desc">' + escapeHTML(career.shortDescription) + "</p>" +
        '<div class="chip-row">' + skillChips + "</div>" +
        '<div class="career-card-foot">' +
          '<button type="button" class="btn btn-outline btn-sm" data-open-career="' + escapeHTML(career.id) + '">' +
            "View details" +
          "</button>" +
        "</div>";

      card.querySelector("[data-open-career]").addEventListener("click", function () {
        Modal.open(career.id);
      });
      return card;
    }
  };

  /* ------------------------------------------------------------------ *
   * Career detail modal (shared by results and directory)
   * ------------------------------------------------------------------ */

  const Modal = {
    lastFocused: null,
    requestToken: 0,
    currentId: null,

    open: function (careerId) {
      const local = AI.careers.filter(function (c) { return c.id === careerId; })[0];
      if (!local) {
        toast("That career could not be found.");
        return;
      }

      Modal.lastFocused = document.activeElement;
      Modal.currentId = careerId;
      const modal = byId("career-modal");
      const token = ++Modal.requestToken;

      Modal.showLoading(local);
      modal.hidden = false;
      document.body.classList.add("modal-open");
      byId("modal-close").focus();
      Modal.loadDetails(careerId, token);
    },

    showLoading: function (career) {
      byId("modal-body").innerHTML =
        '<div class="modal-loading" role="status">' +
          '<span class="spinner" aria-hidden="true"></span>' +
          '<h2 id="modal-title" class="visually-hidden">Loading career details</h2>' +
          "<p>Loading " + escapeHTML(career.title) + "…</p>" +
        "</div>";
    },

    loadDetails: async function (careerId, token) {
      try {
        const response = await apiFetch("/api/careers/" + encodeURIComponent(careerId));
        if (!response.ok) throw new Error("HTTP " + response.status);
        const career = await response.json();
        if (token !== Modal.requestToken) return;
        Modal.show(career, null);
      } catch (error) {
        if (token !== Modal.requestToken) return;
        const local = AI.careers.filter(function (c) { return c.id === careerId; })[0];
        if (!local) {
          byId("modal-body").innerHTML =
            '<div class="modal-loading"><h2 id="modal-title">Career details unavailable</h2>' +
            "<p>We couldn’t load this career from the service.</p></div>";
          return;
        }
        Modal.show(local, error);
      }
    },

    show: function (career, offlineError) {
      const body = byId("modal-body");
      let notice = "";
      if (offlineError) {
        notice =
          '<div class="modal-offline" role="status">' +
            "<span><strong>Offline demo copy.</strong> The backend could not be reached, " +
            "so this profile comes from the bundled career data.</span>" +
            '<button type="button" class="link-btn" id="modal-retry-details">Retry</button>' +
          "</div>";
      }

      body.innerHTML = notice + Modal.buildContent(career);
      body.querySelectorAll("[data-close-modal]").forEach(function (btn) {
        btn.addEventListener("click", Modal.close);
      });

      const retry = byId("modal-retry-details");
      if (retry) {
        retry.addEventListener("click", function () {
          const token = ++Modal.requestToken;
          Modal.showLoading(career);
          Modal.loadDetails(career.id, token);
        });
      }
    },

    close: function () {
      Modal.requestToken += 1; /* cancel a pending detail request */
      byId("career-modal").hidden = true;
      document.body.classList.remove("modal-open");
      if (Modal.lastFocused && typeof Modal.lastFocused.focus === "function") {
        Modal.lastFocused.focus();
      }
    },

    buildContent: function (career) {
      const p = state.profile;
      const held = Object.keys(p.skills);
      const score = Results.matchScoreFor(career.id);

      const hasSkills = held.length > 0;
      const ownedSkills = career.coreSkills.filter(function (s) {
        return held.indexOf(s) !== -1;
      });
      const gapSkills = career.coreSkills.filter(function (s) {
        return held.indexOf(s) === -1;
      });

      function listItems(items, className) {
        return "<ul class=\"" + (className || "") + "\">" + items.map(function (item) {
          return "<li>" + escapeHTML(item) + "</li>";
        }).join("") + "</ul>";
      }

      function chips(keys, labelMap, cls) {
        return keys.map(function (key) {
          return '<span class="chip ' + cls + '">' + escapeHTML(labelMap[key] || key) + "</span>";
        }).join("");
      }

      /* --- skill gap section (personalised only after an assessment) --- */
      let skillGapHTML;
      if (hasSkills) {
        skillGapHTML =
          '<div class="detail-block skill-gap">' +
            "<h3>Your skill gap for this career</h3>" +
            '<div class="gap-cols">' +
              '<div class="gap-col gap-have">' +
                "<h4>You already have</h4>" +
                (ownedSkills.length
                  ? '<div class="chip-row">' + chips(ownedSkills, AI.SKILL_LABELS, "chip-have") + "</div>"
                  : "<p class=\"gap-none\">No overlap yet with your selected skills.</p>") +
              "</div>" +
              '<div class="gap-col gap-need">' +
                "<h4>Develop next</h4>" +
                (gapSkills.length
                  ? '<div class="chip-row">' + chips(gapSkills, AI.SKILL_LABELS, "chip-gap") + "</div>"
                  : '<p class="gap-none">Core skills already covered — focus on the roadmap below.</p>') +
              "</div>" +
            "</div>" +
          "</div>";
      } else {
        skillGapHTML =
          '<div class="detail-block skill-gap is-neutral">' +
            "<h3>Your skill gap for this career</h3>" +
            '<p class="gap-none">Complete the career assessment and this section will compare ' +
            "your selected skills with this career's core skills.</p>" +
            '<a href="#assessment" class="btn btn-primary btn-sm" data-close-modal>Take the assessment</a>' +
          "</div>";
      }

      /* --- roadmap steps --- */
      const roadmap = career.skillsToLearn.map(function (skill, index) {
        return '<li class="roadmap-step"><span class="roadmap-num">' + (index + 1) +
          "</span><span>" + escapeHTML(skill) + "</span></li>";
      }).join("");

      const resources = career.resources.map(function (resource) {
        return '<li><a href="' + escapeHTML(resource.url) + '" target="_blank" rel="noopener noreferrer">' +
          escapeHTML(resource.label) + "</a></li>";
      }).join("");

      const projects = career.beginnerProjects.map(function (project) {
        return '<li class="project-item"><span class="project-bullet" aria-hidden="true"></span>' +
          escapeHTML(project) + "</li>";
      }).join("");

      const scoreHTML = score !== null
        ? '<div class="modal-score"><strong>' + score + '</strong>' +
          '<span>indicative profile match<br><small>not a success probability</small></span></div>'
        : "";

      return (
        '<header class="modal-head">' +
          '<span class="category-tag">' + escapeHTML(career.category) + "</span>" +
          '<h2 id="modal-title">' + escapeHTML(career.title) + "</h2>" +
          scoreHTML +
          '<p class="modal-lead">' + escapeHTML(career.shortDescription) + "</p>" +
        "</header>" +

        '<div class="detail-block">' +
          "<h3>Career overview</h3>" +
          "<p>" + escapeHTML(career.overview) + "</p>" +
        "</div>" +

        '<div class="detail-block">' +
          "<h3>Typical responsibilities</h3>" +
          listItems(career.responsibilities, "check-list") +
        "</div>" +

        '<div class="detail-block">' +
          "<h3>Required and useful skills</h3>" +
          '<div class="chip-row">' + chips(career.coreSkills, AI.SKILL_LABELS, "chip-skill") + "</div>" +
          '<h4 class="subhead">Skills useful to learn next</h4>' +
          listItems(career.skillsToLearn, "") +
        "</div>" +

        '<div class="detail-block">' +
          "<h3>Relevant subjects</h3>" +
          '<div class="chip-row">' + career.subjects.map(function (subject) {
            return '<span class="chip chip-subject">' + escapeHTML(subject) + "</span>";
          }).join("") + "</div>" +
        "</div>" +

        skillGapHTML +

        '<div class="detail-block">' +
          "<h3>Learning roadmap</h3>" +
          '<ol class="roadmap">' + roadmap + "</ol>" +
        "</div>" +

        '<div class="detail-block">' +
          "<h3>Beginner project ideas</h3>" +
          '<ul class="project-list">' + projects + "</ul>" +
        "</div>" +

        '<div class="detail-block">' +
          "<h3>Learning resources</h3>" +
          '<ul class="resource-list">' + resources + "</ul>" +
          '<p class="detail-note">General guidance only. Specific entry requirements ' +
          "differ by employer and institution — " + escapeHTML(career.educationNote) + "</p>" +
        "</div>" +

        '<div class="detail-block">' +
          "<h3>Typical education pathways</h3>" +
          listItems(career.educationPathways, "pathway-list") +
        "</div>" +

        '<div class="detail-block">' +
          "<h3>Work styles seen in this role</h3>" +
          '<div class="chip-row">' + chips(career.workStyles, AI.WORK_STYLE_LABELS, "chip-style") + "</div>" +
        "</div>"
      );
    }
  };

  /* Score for a career from the last result (null when no result exists). */
  Results.matchScoreFor = function (careerId) {
    if (!state.lastResult || state.lastResult.status !== "ok") return null;
    const found = state.lastResult.matches.filter(function (m) { return m.id === careerId; })[0];
    return found ? found.score : null;
  };

  /* ------------------------------------------------------------------ *
   * Modal wiring: backdrop, Escape, focus trap
   * ------------------------------------------------------------------ */

  function initModal() {
    const modal = byId("career-modal");
    const dialog = byId("modal-dialog");

    byId("modal-close").addEventListener("click", Modal.close);

    modal.addEventListener("mousedown", function (event) {
      if (event.target === modal) Modal.close();
    });

    document.addEventListener("keydown", function (event) {
      if (modal.hidden) return;

      if (event.key === "Escape") {
        event.preventDefault();
        Modal.close();
        return;
      }

      if (event.key === "Tab") {
        const focusables = dialog.querySelectorAll(
          'a[href], button:not([disabled]), input:not([disabled]), select, textarea, [tabindex]:not([tabindex="-1"])'
        );
        if (focusables.length === 0) return;
        const first = focusables[0];
        const last = focusables[focusables.length - 1];
        if (event.shiftKey && document.activeElement === first) {
          event.preventDefault();
          last.focus();
        } else if (!event.shiftKey && document.activeElement === last) {
          event.preventDefault();
          first.focus();
        }
      }
    });
  }

  /* ------------------------------------------------------------------ *
   * Explore wiring
   * ------------------------------------------------------------------ */

  function initExplore() {
    const search = byId("career-search");
    const clear = byId("search-clear");
    let debounce = null;

    search.addEventListener("input", function () {
      Explore.query = search.value;
      clear.hidden = search.value === "";
      clearTimeout(debounce);
      debounce = setTimeout(Explore.render, 140);
    });

    clear.addEventListener("click", function () {
      search.value = "";
      Explore.query = "";
      clear.hidden = true;
      Explore.render();
      search.focus();
    });

    byId("btn-clear-filters").addEventListener("click", function () {
      search.value = "";
      Explore.query = "";
      clear.hidden = true;
      Explore.category = "All";
      Explore.renderChips();
      Explore.render();
      search.focus();
    });
  }

  /* ------------------------------------------------------------------ *
   * Results wiring
   * ------------------------------------------------------------------ */

  function initResults() {
    byId("btn-more-results").addEventListener("click", Results.toggleAll);
    byId("btn-retake").addEventListener("click", function () { Results.restart(true); });

    byId("btn-retry-recommendations").addEventListener("click", function () {
      state.api.demoMode = false;
      Results.generate();
    });

    byId("btn-demo-mode").addEventListener("click", function () {
      state.api.demoMode = true;
      Results.generate();
    });

    byId("footer-results-link").addEventListener("click", function (event) {
      if (!state.lastResult) {
        event.preventDefault();
        toast("Complete the assessment first — your results will appear here.");
        byId("assessment").scrollIntoView({ behavior: "smooth", block: "start" });
      }
    });
  }

  /* ------------------------------------------------------------------ *
   * Init
   * ------------------------------------------------------------------ */

  function init() {
    if (!AI || !AI.careers || !AI.RecommendationEngine) {
      document.body.innerHTML =
        '<p style="padding:2rem;font-family:sans-serif">Failed to load career data. ' +
        "Please make sure careers-data.js and recommendation-engine.js are next to index.html.</p>";
      return;
    }

    initNav();
    buildSelects();
    buildSkillsGrid();
    buildCheckboxGrid("interests-grid", AI.INTEREST_ORDER, AI.INTEREST_LABELS, "interests");
    buildCheckboxGrid("styles-grid", AI.WORK_STYLE_ORDER, AI.WORK_STYLE_LABELS, "workStyles");
    buildSubjects();
    initAssessmentNav();
    initResults();
    Explore.renderChips();
    Explore.render();
    initExplore();
    initModal();
    initCounts();
    byId("api-banner-retry").addEventListener("click", loadCatalog);
    showStep(1);
    loadCatalog();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();

