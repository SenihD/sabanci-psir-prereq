const fs=require('fs'),vm=require('vm'),assert=require('assert');
const html=fs.readFileSync(require('path').join(__dirname,'../docs/checker.html'),'utf8');
const data=html.match(/<script id="data" type="application\/json">([\s\S]*?)<\/script>/)[1];
let js=html.match(/<script>([\s\S]*?)<\/script>/)[1].replace(/init\(\);\s*$/, '');
const ctx={document:{getElementById:()=>({textContent:data})},console};vm.createContext(ctx);vm.runInContext(js,ctx);
function run(code){return vm.runInContext(code,ctx);}
assert(run(`planningWarnings(BY_CODE.POLS457,plan.terms[0]).some(w=>w.kind==='danger')`));
assert(run(`planningWarnings(BY_CODE.POLS457,plan.terms[0]).some(w=>w.kind==='season')`));
run(`plan.assignments.POLS250=plan.terms[0].id;plan.assignments.POLS457=plan.terms[0].id`);
assert(run(`planningWarnings(BY_CODE.POLS457,plan.terms[0]).some(w=>w.kind==='danger')`),'same term must warn');
assert(!run(`planningWarnings(BY_CODE.POLS457,plan.terms[1]).some(w=>w.kind==='danger')`),'earlier prerequisite accepted');
assert.equal(run('evaluate().takenCount'),0,'planned courses do not count toward completion');
run(`taken.add('POLS250')`);
assert(!run(`planningWarnings(BY_CODE.POLS457,plan.terms[0]).some(w=>w.kind==='danger')`));
assert(run(`satisfiedBy({op:'or',args:['POLS250','POLS301']},taken)`));
assert(!run(`satisfiedBy({op:'and',args:['POLS250','POLS301']},taken)`));
assert(run(`planningWarnings(BY_CODE.SPS303,plan.terms[0]).some(w=>w.text.includes('58 SU'))`));
assert(run(`planningWarnings(BY_CODE.IR341,plan.terms[0]).some(w=>w.text.includes('Not offered recently'))`));
console.log('Passed: missing/earlier/same-term prerequisites, AND/OR, completed vs planned, seasonal warnings, credit gates, stale offering warning.');
