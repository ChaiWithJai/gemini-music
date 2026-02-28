const el = {
  health: document.querySelector("#out-health"),
  session: document.querySelector("#out-session"),
  mastery: document.querySelector("#out-mastery"),
  ecosystem: document.querySelector("#out-ecosystem"),
  runAll: document.querySelector("#run-all"),
};

const actionButtons = Array.from(document.querySelectorAll("[data-action]"));

function safeId(prefix) {
  if (typeof crypto !== "undefined" && crypto.randomUUID) {
    return `${prefix}-${crypto.randomUUID().slice(0, 8)}`;
  }
  return `${prefix}-${Math.random().toString(36).slice(2, 10)}`;
}

function fmt(data) {
  return JSON.stringify(data, null, 2);
}

function setLog(node, value, ok = true) {
  node.textContent = typeof value === "string" ? value : fmt(value);
  node.classList.toggle("ok", ok);
}

async function api(path, options) {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json", ...(options?.headers || {}) },
    ...options,
  });
  let body = {};
  try {
    body = await res.json();
  } catch (_err) {
    body = { raw: await res.text() };
  }
  if (!res.ok) {
    throw new Error(`${res.status} ${res.statusText}\n${fmt(body)}`);
  }
  return body;
}

async function runHealthBusiness() {
  const health = await api("/health");
  const northStar = await api("/v1/analytics/business-signal/north-star");
  const attribution = await api("/v1/analytics/business-signal/attribution");
  setLog(el.health, {
    health,
    north_star: {
      metric_id: northStar.metric_id,
      metric_name: northStar.name,
      value: northStar.value,
      date_key: northStar.date_key,
    },
    attribution_trend: attribution.trend,
  });
}

async function runSessionFlow() {
  const user = await api("/v1/users", {
    method: "POST",
    body: JSON.stringify({ display_name: `Demo Singer ${new Date().toLocaleTimeString()}` }),
  });

  await api(`/v1/users/${user.id}/consent`, {
    method: "PUT",
    body: JSON.stringify({
      biometric_enabled: true,
      environmental_enabled: true,
      raw_audio_storage_enabled: false,
      policy_version: "v1",
    }),
  });

  const session = await api("/v1/sessions", {
    method: "POST",
    body: JSON.stringify({
      user_id: user.id,
      intention: "Demo route scenario",
      mantra_key: "maha_mantra_hare_krishna_hare_rama",
      mood: "anxious",
      target_duration_minutes: 10,
    }),
  });

  await api(`/v1/sessions/${session.id}/events`, {
    method: "POST",
    body: JSON.stringify({
      event_type: "voice_window",
      client_event_id: safeId("demo-voice"),
      payload: {
        cadence_bpm: 82,
        pronunciation_score: 0.64,
        flow_score: 0.59,
        practice_seconds: 620,
        heart_rate: 118,
        noise_level_db: 53,
      },
    }),
  });

  const adaptation = await api(`/v1/sessions/${session.id}/adaptations`, {
    method: "POST",
    body: JSON.stringify({ explicit_mood: "anxious" }),
  });

  const ended = await api(`/v1/sessions/${session.id}/end`, {
    method: "POST",
    body: JSON.stringify({ user_value_rating: 5, completed_goal: true }),
  });

  const bhav = await api(`/v1/sessions/${session.id}/bhav`, {
    method: "POST",
    body: JSON.stringify({
      golden_profile: "maha_mantra_v1",
      lineage: "vaishnavism",
      persist: false,
    }),
  });

  setLog(el.session, {
    user_id: user.id,
    session_id: session.id,
    adaptation: {
      tempo_bpm: adaptation.tempo_bpm,
      guidance_intensity: adaptation.guidance_intensity,
      key_center: adaptation.key_center,
      contract_quality: adaptation.adaptation_json?.contract?.quality_score,
    },
    summary: ended.summary,
    bhav: {
      composite: bhav.composite,
      passes_golden: bhav.passes_golden,
      lineage: bhav.lineage_id,
    },
  });
}

async function runStageMatrix() {
  const base = {
    lineage: "vaishnavism",
    golden_profile: "maha_mantra_v1",
  };

  const guided = await api("/v1/maha-mantra/evaluate", {
    method: "POST",
    body: JSON.stringify({
      ...base,
      stage: "guided",
      metrics: {
        duration_seconds: 34,
        voice_ratio_total: 0.6,
        voice_ratio_student: 0.6,
        voice_ratio_guru: 0,
        pitch_stability: 0.79,
        cadence_bpm: 72,
        cadence_consistency: 0.77,
        avg_energy: 0.45,
      },
    }),
  });

  const callResponse = await api("/v1/maha-mantra/evaluate", {
    method: "POST",
    body: JSON.stringify({
      ...base,
      stage: "call_response",
      metrics: {
        duration_seconds: 38,
        voice_ratio_total: 0.65,
        voice_ratio_student: 0.72,
        voice_ratio_guru: 0.18,
        pitch_stability: 0.82,
        cadence_bpm: 72,
        cadence_consistency: 0.81,
        avg_energy: 0.48,
      },
    }),
  });

  const independent = await api("/v1/maha-mantra/evaluate", {
    method: "POST",
    body: JSON.stringify({
      ...base,
      stage: "independent",
      metrics: {
        duration_seconds: 30,
        voice_ratio_total: 0.74,
        voice_ratio_student: 0.74,
        voice_ratio_guru: 0,
        pitch_stability: 0.86,
        cadence_bpm: 71,
        cadence_consistency: 0.86,
        avg_energy: 0.5,
      },
    }),
  });

  setLog(el.mastery, {
    guided: {
      composite: guided.composite,
      mastery: guided.metrics_used?.mastery,
    },
    call_response: {
      composite: callResponse.composite,
      mastery: callResponse.metrics_used?.mastery,
    },
    independent: {
      composite: independent.composite,
      mastery: independent.metrics_used?.mastery,
    },
    progression_delta: Number((independent.composite - guided.composite).toFixed(3)),
  });
}

async function runEcosystemReliability() {
  const user = await api("/v1/users", {
    method: "POST",
    body: JSON.stringify({ display_name: `Adapter User ${new Date().toISOString()}` }),
  });

  const session = await api("/v1/sessions", {
    method: "POST",
    body: JSON.stringify({
      user_id: user.id,
      intention: "ecosystem demo",
      mantra_key: "om_namah_shivaya",
      mood: "neutral",
      target_duration_minutes: 8,
    }),
  });

  await api("/v1/integrations/webhooks", {
    method: "POST",
    body: JSON.stringify({
      target_url: `https://example.org/hook/${safeId("demo")}`,
      adapter_id: "content_playlist_adapter",
      event_types: ["session_ended", "adaptation_applied"],
      is_active: true,
    }),
  });

  await api("/v1/integrations/events", {
    method: "POST",
    body: JSON.stringify({
      session_id: session.id,
      partner_source: "wearable_reference_partner",
      adapter_id: "wearable_hr_stream",
      event_type: "partner_signal",
      client_event_id: safeId("wearable"),
      payload: { signal_type: "heart_rate", heart_rate: 109, cadence_bpm: 73, practice_seconds: 120 },
    }),
  });

  await api(`/v1/sessions/${session.id}/end`, {
    method: "POST",
    body: JSON.stringify({ user_value_rating: 4.8, completed_goal: true }),
  });

  const webhookProcess = await api("/v1/admin/webhooks/process?ignore_schedule=true", { method: "POST" });
  const ecosystem = await api("/v1/integrations/exports/ecosystem-usage/daily");

  setLog(el.ecosystem, {
    webhook_process: webhookProcess,
    ecosystem_daily: ecosystem,
  });
}

const actions = {
  health: runHealthBusiness,
  session: runSessionFlow,
  mastery: runStageMatrix,
  ecosystem: runEcosystemReliability,
};

async function runAction(name) {
  const node = el[name];
  const btn = document.querySelector(`[data-action="${name}"]`);
  if (!node || !btn) return;
  btn.disabled = true;
  setLog(node, "Running...", true);
  try {
    await actions[name]();
  } catch (err) {
    setLog(node, err instanceof Error ? err.message : String(err), false);
  } finally {
    btn.disabled = false;
  }
}

actionButtons.forEach((button) => {
  button.addEventListener("click", () => runAction(button.dataset.action));
});

el.runAll?.addEventListener("click", async () => {
  el.runAll.disabled = true;
  for (const name of ["health", "session", "mastery", "ecosystem"]) {
    // eslint-disable-next-line no-await-in-loop
    await runAction(name);
  }
  el.runAll.disabled = false;
});
