
import "dotenv/config";
import express from "express";
import { intakeConfig, validateInquiry, saveInquiry, makeRateLimiter } from "./inquiries.mjs";
import { staffConfig, authorizeStaff, validateStatusChange, listStaffInquiries, appendStatus } from "./staff.mjs";
import { validateCredentials, bearerToken } from "./auth.mjs";
import { postgresConfig, openDatabase, loginStaff, findSession, revokeSession, addInquiry, getInquiries, setInquiryStatus } from "./postgres.mjs";
import { buildKnowledgeContext } from "./knowledge.mjs";

const app = express();
const intake = intakeConfig();
const staff = staffConfig();
const dbConfig = postgresConfig();
const database = dbConfig.enabled ? await openDatabase(dbConfig) : null;
const allowLogin = makeRateLimiter({ limit: 5, windowMs: 5 * 60_000 });
const allowInquiry = makeRateLimiter();

const PORT = Number(process.env.PORT || 3000);
const OLLAMA_URL = "http://127.0.0.1:11434";
const MODEL = process.env.OLLAMA_MODEL || "gemma3:4b";

app.disable("x-powered-by");
app.use(express.json({ limit: "8mb" }));
app.use(express.static("public"));

const SYSTEM = `
You are Ask Troy, American Tree Colorado's AI
tree-care assistant.

Troy is an ISA Certified Arborist. You are an AI,
not Troy, and do not personally hold ISA certification.

Provide practical, research-informed guidance about
Colorado trees, pests, diseases, roots, soil, watering,
pruning, planting, and tree preservation.

Ask one or two useful questions at a time.

Never claim to have inspected a tree or confirmed a
disease from insufficient evidence. When looking at
photos, distinguish visible symptoms from possibilities.

Consider species, symptom location, timing, soil,
watering, roots, construction, and environmental stress.

Do not automatically recommend chemicals, injections,
fertilization, pruning, or removal.

Never declare a tree structurally safe or perform
a formal remote tree risk assessment.

For suspected hanging limbs, instability, or electrical
hazards, prioritize keeping people away. Recommend
appropriate qualified professionals or utilities.
Never provide dangerous DIY cutting or climbing advice.

Do not invent service area coverage, prices,
appointment availability, or confirmed submissions.

American Tree Colorado:
Phone: 303-456-6898
Contact: https://americantreecolorado.com/contact

This prototype cannot send inquiries or book appointments.

Be friendly, practical, and concise, normally under
160 words. Troy's personal interview knowledge
is intentionally excluded.
`;

const danger =
  /\b(power lines?|electrical wires?|hanging limbs?|broken branches?|cracked (?:limb|branch|trunk)|tree (?:is )?falling|sudden(?:ly)? lean(?:ing)?|roots? (?:lifting|heaving))\b/i;

const safetyNote =
  "⚠️ If a tree or large branch may be unstable, " +
  "keep people and vehicles away. Do not try to " +
  "cut or remove it. For electrical hazards, stay " +
  "clear and contact the utility. If people are " +
  "in immediate danger, contact emergency services.";

async function requireStaff(req, res, next) {
  res.set("Cache-Control", "no-store");
  if (database) {
    try {
      const token = bearerToken(req.get("authorization"));
      const user = token ? await findSession(database, token) : null;
      if (!user) return res.status(401).json({ error: "Staff authorization required." });
      req.staffUser = user;
      return next();
    } catch(error) {
      console.error("Session lookup failed:", error.message);
      return res.status(503).json({ error: "Staff session unavailable." });
    }
  }
  res.set("Cache-Control", "no-store");
  if (!authorizeStaff(req.get("authorization"), staff)) {
    return res.status(401).json({ error: "Staff authorization required." });
  }
  next();
}

app.post("/api/staff/login", async (req, res) => {
  res.set("Cache-Control", "no-store");
  if (!database) return res.status(503).json({ error: "Individual staff login is not enabled." });
  if (!allowLogin(req.ip || "local")) return res.status(429).json({ error: "Too many login attempts." });
  const credentials = validateCredentials(req.body);
  if (!credentials) return res.status(400).json({ error: "Invalid credentials." });
  try {
    const session = await loginStaff(database, credentials);
    if (!session) return res.status(401).json({ error: "Invalid credentials." });
    return res.json(session);
  } catch(error) {
    console.error("Staff login unavailable:", error.message);
    return res.status(503).json({ error: "Staff login unavailable." });
  }
});
app.post("/api/staff/logout", requireStaff, async (req, res) => {
  if (!database) return res.status(400).json({ error: "Database session not enabled." });
  try {
    await revokeSession(database, bearerToken(req.get("authorization")));
    return res.json({ loggedOut: true });
  } catch(error) {
    console.error("Logout failed:", error.message);
    return res.status(503).json({ error: "Unable to log out." });
  }
});

app.get("/api/staff/inquiries", requireStaff, async (_req, res) => {
  try {
    const items = database ? await getInquiries(database) : await listStaffInquiries(staff.file);
    res.json({ items, count: items.length });
  } catch (error) {
    console.error("Unable to list staff inquiries:", error.message);
    res.status(503).json({ error: "Unable to load inquiries." });
  }
});

app.patch("/api/staff/inquiries/:id", requireStaff, async (req, res) => {
  const change = validateStatusChange(req.params.id, req.body);
  if (!change.ok) return res.status(400).json({ error: change.error });
  try {
    if (database) {
      const updated = await setInquiryStatus(database, { ...change.value, staffId: req.staffUser.staff_id });
      if (!updated) return res.status(404).json({ error: "Inquiry not found." });
      return res.json({ updated: true, reference: change.value.id, status: change.value.status });
    }
    const items = await listStaffInquiries(staff.file);
    if (!items.some(item => item.id === change.value.id)) {
      return res.status(404).json({ error: "Inquiry not found." });
    }
    const event = await appendStatus(staff.file, change.value);
    res.json({ updated: true, reference: event.id, status: event.status, updatedAt: event.createdAt });
  } catch (error) {
    console.error("Unable to update inquiry:", error.message);
    res.status(503).json({ error: "Unable to update inquiry." });
  }
});

app.get("/api/inquiry/config", (req, res) => {
  res.set("Cache-Control", "no-store");
  res.json({ enabled: intake.enabled, photosSupported: false, delivery: database ? "private-database" : "local-queue" });
});

app.post("/api/inquiries", async (req, res) => {
  res.set("Cache-Control", "no-store");
  if (!intake.enabled) return res.status(503).json({
    error: "Online inquiry submission is not enabled. Please use the official contact page or call."
  });

  // Prevent cross-origin browser submissions. This is not an internet-facing CSRF solution.
  const origin = req.get("origin");
  if (origin) {
    let parsed;
    try { parsed = new URL(origin); } catch { return res.status(403).json({ error: "Invalid origin." }); }
    if (parsed.host !== req.get("host") || parsed.protocol !== req.protocol + ":") {
      return res.status(403).json({ error: "Cross-origin submission blocked." });
    }
  }
  if (!allowInquiry(req.ip || "local")) {
    return res.status(429).json({ error: "Too many inquiries. Please try again later." });
  }
  const parsed = validateInquiry(req.body);
  if (parsed.spam) return res.status(202).json({ accepted: false, message: "Request received for processing." });
  if (!parsed.ok) return res.status(400).json({ error: parsed.error });
  try {
    const saved = database ? await addInquiry(database, parsed.value) : await saveInquiry(parsed.value, intake);
    return res.status(201).json({
      accepted: true,
      reference: saved.id,
      createdAt: saved.createdAt,
      status: database ? "saved-to-database" : "saved-locally",
      deliveredToOffice: false,
      message: database ? "Inquiry saved to the private database for staff review. The office has not been notified automatically." : "Inquiry saved to a local queue for staff review. The office has not been notified automatically."
    });
  } catch (error) {
    console.error("Inquiry storage failed:", error.message);
    return res.status(503).json({ error: "Unable to save your inquiry. Please call or use the official contact page." });
  }
});

app.get("/api/health", async (req, res) => {
  try {
    const response = await fetch(
      `${OLLAMA_URL}/api/tags`,
      { signal: AbortSignal.timeout(5000) }
    );

    if (!response.ok) throw new Error("Ollama unavailable");

    const data = await response.json();
    const installed = data.models?.some(
      m => m.name === MODEL || m.model === MODEL
    );

    res.json({
      ollama: "online",
      model: MODEL,
      installed,
      local: true
    });
  } catch {
    res.status(503).json({
      ollama: "offline",
      model: MODEL,
      installed: false
    });
  }
});

app.post("/api/chat", async (req, res) => {
  try {
    const { message, history = [], image = null } = req.body;

    if (typeof message !== "string" ||
        !message.trim() ||
        message.length > 2000) {
      return res.status(400).json({
        error: "Enter a message of 1–2000 characters."
      });
    }

    if (!Array.isArray(history) || history.length > 20) {
      return res.status(400).json({
        error: "Invalid conversation history."
      });
    }

    if (image !== null &&
        (typeof image !== "string" ||
         image.length > 7_000_000 ||
         !/^data:image\/(jpeg|png|webp);base64,/.test(image))) {
      return res.status(400).json({
        error: "Invalid image. Use JPG, PNG, or WebP."
      });
    }

    const { context: knowledgeContext, sources } = buildKnowledgeContext(message);

    const previous = history
      .filter(h =>
        h &&
        ["user", "assistant"].includes(h.role) &&
        typeof h.content === "string" &&
        h.content.length <= 3000
      )
      .slice(-12)
      .map(h => ({
        role: h.role,
        content: h.content
      }));

    const userMessage = {
      role: "user",
      content: message
    };

    if (image) {
      userMessage.images = [
        image.replace(
          /^data:image\/(?:jpeg|png|webp);base64,/,
          ""
        )
      ];
    }

    const response = await fetch(
      `${OLLAMA_URL}/api/chat`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          model: MODEL,
          stream: false,
          messages: [
            { role: "system", content: SYSTEM + (knowledgeContext ? "\n\n" + knowledgeContext : "") },
            ...previous,
            userMessage
          ],
          options: {
            temperature: 0.3,
            num_ctx: 8192
          }
        }),
        signal: AbortSignal.timeout(180000)
      }
    );

    if (!response.ok) {
      const details = await response.text();
      console.error("Ollama error:", details);
      throw new Error("Model response failed.");
    }

    const data = await response.json();

    let answer = data.message?.content?.trim();

    if (!answer) {
      throw new Error("Empty model response.");
    }

    if (danger.test(message)) {
      answer = `${safetyNote}\n\n${answer}`;
    }

    res.json({
      answer,
      model: MODEL,
      local: true,
      submitted: false,
      booked: false,
      sources
    });

  } catch (error) {
    console.error("Ask Troy error:", error.message);

    res.status(503).json({
      error:
        "Unable to reach the local AI model. " +
        "Check that Ollama is running and " +
        "the selected model is installed."
    });
  }
});

app.listen(PORT, "127.0.0.1", () => {
  console.log(
    `Ask Troy running at http://127.0.0.1:${PORT}`
  );
  console.log(`Ollama model: ${MODEL}`);
});
