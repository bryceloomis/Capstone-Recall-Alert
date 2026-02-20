/** V2: Ingredient preferences step 1 — intro to the step-through flow. */
export function V2DemoIntro() {
  return (
    <div className="max-w-2xl mx-auto space-y-6">
      <p className="text-[#888] text-sm">V2: Ingredient preferences</p>
      <h2 className="text-xl font-semibold text-[#1A1A1A]">
        Ingredient preferences & food preferences
      </h2>
      <p className="text-[#888] text-sm leading-relaxed">
        This flow walks through the stretch-goal experience: choose ingredients to avoid, see how cart scan results flag products that contain them, get recommendations for alternatives, and manage ingredient restrictions.
      </p>
      <ul className="text-sm text-[#888] space-y-2 list-disc list-inside">
        <li>Step 1: Intro (this screen)</li>
        <li>Step 2: Cart scan results with ingredient match</li>
        <li>Step 3: Similar products without your avoided ingredients</li>
        <li>Step 4: Ingredient preferences</li>
        <li>Step 5: Ingredients to avoid</li>
      </ul>
      <p className="text-xs text-[#888] pt-2">
        Use the arrows in the top bar to move through the steps.
      </p>
    </div>
  );
}
