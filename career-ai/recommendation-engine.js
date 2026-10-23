/*
 * recommendation-engine.js
 * Rule-based prototype recommendation engine for CareerAI.
 *
 * IMPORTANT: This is a transparent, rule-based matching prototype — it is NOT a
 * trained AI model and produces no confidence probabilities. Scores are
 * "indicative profile matches" only.
 *
 * Scoring model (all components normalized to 0–1 before weighting):
 *
 *   Component     Weight   How it is computed
 *   ------------  -------  ---------------------------------------------------
 *   Skills        40%      Average of career core skills the student selected,
 *                          each weighted by self-rated proficiency (1–5 => 0.2–1.0)
 *   Interests     25%      Overlap coefficient: |interests in common| /
 *                          min(|student interests|, |career interests|)
 *   Academics     20%      Weighted average of the student's marks over the
 *                          subjects the career cares about (0–100 => 0–1)
 *   Preferences   15%      Overlap coefficient on preferred work styles
 *
 * Missing information is handled by redistributing the weight of unavailable
 * components across the remaining available ones. The final score is then
 * scaled by (0.5 + 0.5 x coverage), where coverage is the total weight of the
 * sections the student answered — so an incomplete profile cannot reach a
 * perfect 100. If fewer than two components are available the engine reports
 * "insufficient" instead of inventing a score.
 *
 * The UI only ever calls getRecommendations(profile), which is async so a REST
 * backend can replace the local calculation later without touching script.js.
 */
(function () {
  "use strict";

  window.CareerAI = window.CareerAI || {};

  /* Future integration seam: set this to a REST endpoint (for example
   * "/api/recommendations") and the UI will call your backend instead of the
   * local rules. Kept null for this first version — no API, key, or service. */
  const CONFIG = { apiEndpoint: null };

  /* Documented weights, also shown in the About section of the site. */
  const WEIGHTS = Object.freeze({
    skills: 0.40,
    interests: 0.25,
    academics: 0.20,
    preferences: 0.15
  });

  const TOP_N = 5;

  /* Which career categories relate to which academic branches. Used for an
   * informational note only — it never affects the score. */
  const BRANCH_RELEVANCE = {
    "computer-science": ["Software & Technology", "Data & AI"],
    "electronics": ["Engineering"],
    "electrical": ["Engineering"],
    "mechanical": ["Engineering"],
    "civil": ["Engineering"],
    "science": ["Science & Research", "Data & AI"],
    "commerce": ["Business & Finance"],
    "arts": ["Media & Communication", "Education"],
    "other": []
  };

  /* ------------------------------------------------------------------ *
   * Helpers
   * ------------------------------------------------------------------ */

  function clamp01(value) {
    if (typeof value !== "number" || !isFinite(value)) return 0;
    return Math.min(1, Math.max(0, value));
  }

  function labelsFor(keys, labelMap) {
    return keys.map(function (key) {
      return labelMap[key] || key;
    });
  }

  function intersection(a, b) {
    const setB = new Set(b);
    return a.filter(function (item) { return setB.has(item); });
  }

  /* ------------------------------------------------------------------ *
   * Component scores (each returns a value 0–1, or null = unavailable)
   * ------------------------------------------------------------------ */

  function scoreSkills(profile, career) {
    const selected = profile.skills || {};
    const heldKeys = Object.keys(selected);
    if (heldKeys.length === 0 || !career.coreSkills || career.coreSkills.length === 0) {
      return null;
    }
    let total = 0;
    career.coreSkills.forEach(function (skill) {
      if (Object.prototype.hasOwnProperty.call(selected, skill)) {
        const rating = selected[skill];
        total += clamp01(rating / 5);
      }
    });
    return total / career.coreSkills.length;
  }

  function scoreInterests(profile, career) {
    const user = profile.interests || [];
    const target = career.interests || [];
    if (user.length === 0 || target.length === 0) return null;
    const shared = intersection(user, target).length;
    return clamp01(shared / Math.min(user.length, target.length));
  }

  function scoreAcademics(profile, career) {
    const marks = profile.subjects || {};
    const weights = career.subjectWeights || {};
    let weighted = 0;
    let totalWeight = 0;
    Object.keys(weights).forEach(function (subject) {
      const mark = marks[subject];
      if (typeof mark === "number" && isFinite(mark)) {
        weighted += weights[subject] * mark;
        totalWeight += weights[subject];
      }
    });
    if (totalWeight === 0) return null; /* student skipped every relevant subject */
    return clamp01((weighted / totalWeight) / 100);
  }

  function scorePreferences(profile, career) {
    const user = profile.workStyles || [];
    const target = career.workStyles || [];
    if (user.length === 0 || target.length === 0) return null;
    const shared = intersection(user, target).length;
    return clamp01(shared / Math.min(user.length, target.length));
  }

  /* ------------------------------------------------------------------ *
   * Explainability: human-readable reasons and skill gaps
   * ------------------------------------------------------------------ */

  function buildReasons(profile, career, components) {
    const reasons = [];
    const L = CareerAI.SKILL_LABELS;
    const IL = CareerAI.INTEREST_LABELS;
    const WL = CareerAI.WORK_STYLE_LABELS;
    const SL = CareerAI.SUBJECT_LABELS;

    const held = profile.skills || {};
    const matchedSkills = career.coreSkills.filter(function (s) {
      return Object.prototype.hasOwnProperty.call(held, s);
    });
    if (matchedSkills.length > 0 && components.skills !== null) {
      const strong = matchedSkills.filter(function (s) { return held[s] >= 4; });
      let text = "Matches " + matchedSkills.length + " of " + career.coreSkills.length +
        " core skills (" + labelsFor(matchedSkills, L).join(", ") + ")";
      if (strong.length >= 2) {
        text += ", several of which you rated as advanced";
      }
      reasons.push(text + ".");
    }

    const sharedInterests = intersection(profile.interests || [], career.interests || []);
    if (sharedInterests.length > 0 && components.interests !== null) {
      reasons.push("You selected the interests " +
        labelsFor(sharedInterests, IL).join(" and ") +
        ", which sit at the centre of this work.");
    }

    if (components.academics !== null) {
      const marks = profile.subjects || {};
      const relevant = Object.keys(career.subjectWeights || {}).filter(function (s) {
        return typeof marks[s] === "number";
      });
      if (relevant.length > 0) {
        const parts = relevant.map(function (s) {
          return (SL[s] || s) + " (" + marks[s] + "%)";
        });
        reasons.push("Your marks in " + parts.join(", ") +
          " are relevant to this career's typical subject focus.");
      }
    }

    const sharedStyles = intersection(profile.workStyles || [], career.workStyles || []);
    if (sharedStyles.length > 0 && components.preferences !== null) {
      reasons.push("Your preferred work style — " +
        labelsFor(sharedStyles, WL).join(", ") +
        " — is central to how this role is carried out.");
    }

    const branch = profile.branch;
    if (branch && (BRANCH_RELEVANCE[branch] || []).indexOf(career.category) !== -1) {
      const branchLabel = (CareerAI.BRANCHES.filter(function (b) {
        return b.value === branch;
      })[0] || {}).label || branch;
      reasons.push("Your academic background (" + branchLabel +
        ") relates directly to this field.");
    }

    if (reasons.length === 0) {
      reasons.push("This career shares some ground with the information you provided, " +
        "but the profile was too limited for a strong signal.");
    }
    return reasons;
  }

  function buildSkillGaps(profile, career) {
    const held = profile.skills || {};
    return career.coreSkills.filter(function (s) {
      return !Object.prototype.hasOwnProperty.call(held, s);
    });
  }

  /* ------------------------------------------------------------------ *
   * Main calculation
   * ------------------------------------------------------------------ */

  function profileAvailability(profile) {
    const held = profile.skills || {};
    return {
      skills: Object.keys(held).length > 0,
      interests: (profile.interests || []).length > 0,
      academics: Object.keys(profile.subjects || {}).some(function (k) {
        return typeof profile.subjects[k] === "number";
      }),
      preferences: (profile.workStyles || []).length > 0
    };
  }

  function computeMatches(profile, careers) {
    const availability = profileAvailability(profile);
    const availableKeys = Object.keys(WEIGHTS).filter(function (key) {
      return availability[key];
    });

    if (availableKeys.length < 2) {
      return {
        status: "insufficient",
        source: "local-rule-based",
        message: "There is not enough information to rank careers yet. " +
          "Please complete at least two sections of the assessment " +
          "(skills, interests, academics, or work preferences).",
        matches: []
      };
    }

    const weightTotal = availableKeys.reduce(function (sum, key) {
      return sum + WEIGHTS[key];
    }, 0);

    /* Coverage: how much of the profile the student actually answered (0–1).
     * Scores are scaled by (0.5 + 0.5 * coverage) so an incomplete profile
     * cannot reach a perfect 100 through weight redistribution alone. */
    const coverage = weightTotal;

    const matches = careers.map(function (career) {
      const raw = {
        skills: scoreSkills(profile, career),
        interests: scoreInterests(profile, career),
        academics: scoreAcademics(profile, career),
        preferences: scorePreferences(profile, career)
      };

      /* Redistribute weight across components that exist for this comparison. */
      let score = 0;
      let usedWeight = 0;
      const usedWeights = {};
      Object.keys(WEIGHTS).forEach(function (key) {
        if (raw[key] === null || !availability[key]) return;
        const normalizedWeight = WEIGHTS[key] / weightTotal;
        score += normalizedWeight * raw[key];
        usedWeight += normalizedWeight;
        usedWeights[key] = normalizedWeight;
      });
      score = usedWeight > 0 ? score / usedWeight : 0;
      score = score * (0.5 + 0.5 * coverage);

      const components = {
        skills: raw.skills === null ? null : Math.round(raw.skills * 100),
        interests: raw.interests === null ? null : Math.round(raw.interests * 100),
        academics: raw.academics === null ? null : Math.round(raw.academics * 100),
        preferences: raw.preferences === null ? null : Math.round(raw.preferences * 100)
      };

      const matchedSkills = career.coreSkills.filter(function (s) {
        return Object.prototype.hasOwnProperty.call(profile.skills || {}, s);
      });
      const matchedInterests = intersection(profile.interests || [], career.interests || []);

      return {
        id: career.id,
        title: career.title,
        category: career.category,
        shortDescription: career.shortDescription,
        score: Math.round(clamp01(score) * 100),
        components: components,
        weightsUsed: usedWeights,
        matchedSkills: matchedSkills,
        matchedInterests: matchedInterests,
        reasons: buildReasons(profile, career, raw),
        skillGaps: buildSkillGaps(profile, career)
      };
    });

    matches.sort(function (a, b) {
      if (b.score !== a.score) return b.score - a.score;
      const aSkills = a.components.skills === null ? -1 : a.components.skills;
      const bSkills = b.components.skills === null ? -1 : b.components.skills;
      if (bSkills !== aSkills) return bSkills - aSkills;
      return a.title.localeCompare(b.title);
    });

    matches.forEach(function (match, index) { match.rank = index + 1; });

    return { status: "ok", source: "local-rule-based", matches: matches, topN: TOP_N,
             coverage: Math.round(coverage * 100) };
  }

  /* ------------------------------------------------------------------ *
   * Public async seam — swap in a REST backend later without UI changes.
   * ------------------------------------------------------------------ */

  async function getRecommendations(profile) {
    if (CONFIG.apiEndpoint) {
      try {
        const response = await fetch(CONFIG.apiEndpoint, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(profile)
        });
        if (!response.ok) throw new Error("Request failed: " + response.status);
        const data = await response.json();
        data.source = "remote-api";
        return data;
      } catch (error) {
        /* Fall back to local rules so the UI keeps working. */
        const fallback = computeMatches(profile, CareerAI.careers);
        fallback.source = "local-rule-based-fallback";
        return fallback;
      }
    }
    /* Small artificial delay so the UI can show honest processing feedback. */
    await new Promise(function (resolve) { setTimeout(resolve, 550); });
    return computeMatches(profile, CareerAI.careers);
  }

  CareerAI.RecommendationEngine = Object.freeze({
    WEIGHTS: WEIGHTS,
    CONFIG: CONFIG,
    getRecommendations: getRecommendations,
    /* Exposed for testing / future backend parity checks. */
    computeMatches: computeMatches
  });
})();
