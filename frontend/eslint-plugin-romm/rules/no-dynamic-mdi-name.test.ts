import rule from "./no-dynamic-mdi-name.js";
import { ruleTester, sfcTemplate } from "./testing";

const dynamic = { messageId: "dynamic" };

ruleTester.run("no-dynamic-mdi-name", rule, {
  valid: [
    'const icon = "mdi-home";',
    "const icon = `mdi-home`;",
    "const label = `${count} items`;",
    "const cls = `mdi-home ${tone}`;",
    'const cls = "mdi-home " + tone;',
    'const cls = "mdi-home" + " " + tone;',
    'const icons = { ok: "mdi-check", bad: "mdi-close" }; const icon = icons[kind];',
    "const url = `/api/amdi-${id}`;",
    "const key = `my_mdi-${id}`;",
    sfcTemplate('<RIcon icon="mdi-home" />'),
    sfcTemplate("<RIcon :icon=\"ok ? 'mdi-check' : 'mdi-close'\" />"),
  ],
  invalid: [
    { code: "const icon = `mdi-${name}`;", errors: [dynamic] },
    { code: "const icon = `mdi-${name}-outline`;", errors: [dynamic] },
    { code: "const icon = `mdi-home-${state}`;", errors: [dynamic] },
    { code: "const icon = `a ${x} mdi-${name}`;", errors: [dynamic] },
    { code: 'const icon = "mdi-" + name;', errors: [dynamic] },
    { code: 'const icon = "mdi-" + "home";', errors: [dynamic] },
    { code: 'const icon = "mdi-home-" + state;', errors: [dynamic] },
    { code: 'const icon = "mdi-" + name + "-outline";', errors: [dynamic] },
    { code: 'const icon = base + " mdi-" + name;', errors: [dynamic] },
    { code: "const icon = `mdi-` + name;", errors: [dynamic] },
    { ...sfcTemplate('<RIcon :icon="`mdi-${name}`" />'), errors: [dynamic] },
    { ...sfcTemplate("<RIcon :icon=\"'mdi-' + name\" />"), errors: [dynamic] },
    {
      ...sfcTemplate("<RIcon :icon=\"base + ' mdi-' + name\" />"),
      errors: [dynamic],
    },
  ],
});
