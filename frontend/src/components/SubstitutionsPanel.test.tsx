import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { HttpResponse, http } from "msw";
import { describe, expect, it } from "vitest";

import { recipe, substitutions } from "../test/handlers";
import { renderWithQuery } from "../test/render";
import { server } from "../test/server";
import { SubstitutionsPanel } from "./SubstitutionsPanel";

const API = "http://localhost:8000";
const BUTTON = "Suggest substitutions";

/** Count what reaches the API, so "nothing is requested" can be asserted directly. */
function countRequests() {
  let calls = 0;
  server.events.on("request:start", ({ request }) => {
    if (request.method === "POST" && request.url.includes("/substitutions"))
      calls += 1;
  });
  return () => calls;
}

/** Record the `ingredient_ids` of each request, which is what the checkboxes decide. */
function captureSelections() {
  const sent: number[][] = [];
  server.use(
    http.post(`${API}/recipes/:id/substitutions`, async ({ request }) => {
      const body = (await request.json()) as { ingredient_ids: number[] };
      sent.push(body.ingredient_ids);
      return HttpResponse.json(substitutions());
    }),
  );
  return sent;
}

function failWith(status: number) {
  server.use(
    http.post(`${API}/recipes/:id/substitutions`, () =>
      HttpResponse.json({ detail: "nope" }, { status }),
    ),
  );
}

describe("SubstitutionsPanel", () => {
  it("asks for nothing until the button is pressed", async () => {
    // The guardrail that matters most: every call spends money, so rendering the panel
    // must cost nothing (spec 14). The press at the end is what proves the counter is
    // actually watching — a counter that never moves would pass the first assertion for
    // the wrong reason.
    const calls = countRequests();
    const user = userEvent.setup();

    renderWithQuery(<SubstitutionsPanel recipe={recipe()} />);

    expect(screen.getByRole("button", { name: BUTTON })).toBeInTheDocument();
    await waitFor(() => expect(calls()).toBe(0));

    await user.click(screen.getByRole("button", { name: BUTTON }));

    await waitFor(() => expect(calls()).toBe(1));
  });

  it("offers nothing at all when the cook has everything", () => {
    const complete = recipe({
      ingredients: recipe().ingredients.map((ingredient) => ({
        ...ingredient,
        owned: true,
      })),
    });

    renderWithQuery(<SubstitutionsPanel recipe={complete} />);

    // No question to ask, so no button to press — not a disabled one.
    expect(
      screen.queryByRole("button", { name: BUTTON }),
    ).not.toBeInTheDocument();
  });

  it("shows the suggestions, labelled as AI-generated, when pressed", async () => {
    const user = userEvent.setup();
    renderWithQuery(<SubstitutionsPanel recipe={recipe()} />);

    await user.click(screen.getByRole("button", { name: BUTTON }));

    expect(await screen.findByText("Butter")).toBeInTheDocument();
    expect(
      screen.getByText("Both carry heat and add richness."),
    ).toBeInTheDocument();
    // The label is not decoration: a suggestion must not be able to pass for a recipe step.
    expect(
      screen.getByRole("heading", { name: /AI-generated suggestions/i }),
    ).toBeInTheDocument();
  });

  it("marks a suggestion the cook already has", async () => {
    const user = userEvent.setup();
    renderWithQuery(<SubstitutionsPanel recipe={recipe()} />);

    await user.click(screen.getByRole("button", { name: BUTTON }));

    expect(await screen.findByText("in your pantry")).toBeInTheDocument();
  });

  it("says so when the model had nothing useful to offer", async () => {
    // Fewer suggestions than missing ingredients is a real answer, not a failure.
    server.use(
      http.post(`${API}/recipes/:id/substitutions`, () =>
        HttpResponse.json(substitutions({ suggestions: [] })),
      ),
    );
    const user = userEvent.setup();
    renderWithQuery(<SubstitutionsPanel recipe={recipe()} />);

    await user.click(screen.getByRole("button", { name: BUTTON }));

    expect(await screen.findByText(/needs a shop/i)).toBeInTheDocument();
  });

  it("renders a partial answer without implying a row is missing", async () => {
    server.use(
      http.post(`${API}/recipes/:id/substitutions`, () =>
        HttpResponse.json(
          substitutions({ suggestions: [substitutions().suggestions[0]!] }),
        ),
      ),
    );
    const user = userEvent.setup();
    renderWithQuery(<SubstitutionsPanel recipe={recipe()} />);

    await user.click(screen.getByRole("button", { name: BUTTON }));

    expect(await screen.findByText("Butter")).toBeInTheDocument();
    expect(screen.queryByText(/needs a shop/i)).not.toBeInTheDocument();
  });

  // --- Choosing what to ask about (spec 10.11) ------------------------------------------
  //
  // A gap is not always a problem to solve. The cook may plan to cook without it, or may
  // own it and never have typed it in — so the panel offers a box to untick and a way to
  // put it in the pantry, and these tests cover both.

  it("offers every missing ingredient, ticked, and asks about all of them", async () => {
    const sent = captureSelections();
    const user = userEvent.setup();
    renderWithQuery(<SubstitutionsPanel recipe={recipe()} />);

    // The two gaps, and only the gaps: what the cook already has is not a question.
    expect(screen.getByRole("checkbox", { name: "Olive Oil" })).toBeChecked();
    expect(screen.getByRole("checkbox", { name: "Salt" })).toBeChecked();
    expect(
      screen.queryByRole("checkbox", { name: "Rice" }),
    ).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: BUTTON }));

    await waitFor(() => expect(sent).toEqual([[4, 5]]));
  });

  it("leaves an unticked ingredient out of the request", async () => {
    // The point of the feature: unticking has to change what is sent, not just what is
    // displayed afterwards. Filtering the answer in the browser would still have paid for
    // the suggestion it then hid.
    const sent = captureSelections();
    const user = userEvent.setup();
    renderWithQuery(<SubstitutionsPanel recipe={recipe()} />);

    await user.click(screen.getByRole("checkbox", { name: "Salt" }));
    expect(screen.getByRole("checkbox", { name: "Salt" })).not.toBeChecked();

    await user.click(
      screen.getByRole("button", { name: "Suggest substitutions for 1" }),
    );

    await waitFor(() => expect(sent).toEqual([[4]]));
  });

  it("counts the choice in the label only once it is a choice", async () => {
    const user = userEvent.setup();
    renderWithQuery(<SubstitutionsPanel recipe={recipe()} />);

    // Everything ticked is the ordinary case, and keeps the plain label.
    expect(screen.getByRole("button", { name: BUTTON })).toBeInTheDocument();

    await user.click(screen.getByRole("checkbox", { name: "Salt" }));

    expect(
      screen.getByRole("button", { name: "Suggest substitutions for 1" }),
    ).toBeInTheDocument();
  });

  it("asks for nothing when every box is unticked", async () => {
    const calls = countRequests();
    const user = userEvent.setup();
    renderWithQuery(<SubstitutionsPanel recipe={recipe()} />);

    await user.click(screen.getByRole("checkbox", { name: "Olive Oil" }));
    await user.click(screen.getByRole("checkbox", { name: "Salt" }));

    // Disabled rather than absent: the boxes above explain why, and the button is where
    // the cook will look once they tick one again.
    const button = screen.getByRole("button", {
      name: "Suggest substitutions for 0",
    });
    expect(button).toBeDisabled();
    expect(
      screen.getByText(/tick something to ask about/i),
    ).toBeInTheDocument();

    await user.click(button);

    await waitFor(() => expect(calls()).toBe(0));
  });

  it("can re-tick what it unticked", async () => {
    const user = userEvent.setup();
    renderWithQuery(<SubstitutionsPanel recipe={recipe()} />);

    await user.click(screen.getByRole("checkbox", { name: "Salt" }));
    await user.click(screen.getByRole("checkbox", { name: "Salt" }));

    expect(screen.getByRole("checkbox", { name: "Salt" })).toBeChecked();
    expect(screen.getByRole("button", { name: BUTTON })).toBeInTheDocument();
  });

  it("puts an ingredient the cook actually has into the pantry", async () => {
    // "I have this" is the other answer to a gap, and the better one: it fixes the pantry
    // rather than hiding the row. That it reaches /pantry/items is what makes the recipe's
    // own count correct itself (asserted end to end in RecipePages.test.tsx).
    let added: number[] = [];
    server.use(
      http.post(`${API}/pantry/items`, async ({ request }) => {
        added = ((await request.json()) as { ingredient_ids: number[] })
          .ingredient_ids;
        return HttpResponse.json([]);
      }),
    );
    const user = userEvent.setup();
    renderWithQuery(<SubstitutionsPanel recipe={recipe()} />);

    const rows = screen.getAllByRole("listitem");
    await user.click(
      within(rows[1]!).getByRole("button", { name: "I have this" }),
    );

    await waitFor(() => expect(added).toEqual([5]));
  });

  it("explains the daily limit", async () => {
    failWith(429);
    const user = userEvent.setup();
    renderWithQuery(<SubstitutionsPanel recipe={recipe()} />);

    await user.click(screen.getByRole("button", { name: BUTTON }));

    expect(await screen.findByText(/try again tomorrow/i)).toBeInTheDocument();
    // Pressing again would spend nothing and change nothing, so there is no retry offered.
    expect(
      screen.queryByRole("button", { name: "Try again" }),
    ).not.toBeInTheDocument();
  });

  it("explains a paused feature", async () => {
    failWith(503);
    const user = userEvent.setup();
    renderWithQuery(<SubstitutionsPanel recipe={recipe()} />);

    await user.click(screen.getByRole("button", { name: BUTTON }));

    expect(
      await screen.findByText(/paused until next month/i),
    ).toBeInTheDocument();
  });

  it("offers a retry for anything else, and the retry works", async () => {
    failWith(502);
    const user = userEvent.setup();
    renderWithQuery(<SubstitutionsPanel recipe={recipe()} />);

    await user.click(screen.getByRole("button", { name: BUTTON }));
    expect(
      await screen.findByRole("button", { name: "Try again" }),
    ).toBeInTheDocument();

    // The model was unreachable, not wrong, so asking again is reasonable.
    server.use(
      http.post(`${API}/recipes/:id/substitutions`, () =>
        HttpResponse.json(substitutions()),
      ),
    );
    await user.click(screen.getByRole("button", { name: "Try again" }));

    expect(await screen.findByText("Butter")).toBeInTheDocument();
  });
});
