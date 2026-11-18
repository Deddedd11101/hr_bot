const {test} = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');

function setup() {
  class Element {
    constructor() { this.children = []; this.dataset = {}; this.style = {}; }
    append(node) { this.children.push(node); }
    replaceChildren() { this.children = []; }
    setAttribute() {}
    addEventListener() {}
  }
  const nodes = {};
  const context = vm.createContext({
    window: {},
    document: {getElementById: id => nodes[id] ??= new Element(), createElement: () => new Element()},
  });
  vm.runInContext(fs.readFileSync('app/static/grade-review.js', 'utf8'), context);
  vm.runInContext(`model = {editable:true, questions:[
    {key:'a',title:'A',options:{1:'One'},skip:'Skip'},
    {key:'b',title:'B',options:{1:'One'},skip:'Skip'},
    {key:'c',title:'C',options:{1:'One'},skip:'Skip'}
  ]}; answers = {a:null};`, context);
  return {context, nodes};
}

test('sequential navigation hides summary and proceeds after a skipped question', () => {
  const {context, nodes} = setup();
  vm.runInContext('render()', context);
  assert.equal(nodes.actions.children.some(n => n.textContent === 'Все ответы'), false);
  nodes.actions.children.at(-1).onclick();
  assert.equal(vm.runInContext('index', context), 1);
});

test('incomplete summary resumes first unanswered, not a skipped question', () => {
  const {context, nodes} = setup();
  vm.runInContext('go(2, true)', context);
  nodes.actions.children.find(n => n.textContent === 'Продолжить опрос').onclick();
  assert.equal(vm.runInContext('index', context), 1);
  assert.equal(vm.runInContext('reviewing', context), false);
});

test('editing from summary returns to summary and completed survey has no resume', () => {
  const {context, nodes} = setup();
  vm.runInContext('answers = {a:null,b:1,c:1}; editingFromSummary=true; go(1)', context);
  nodes.actions.children.at(-1).onclick();
  assert.equal(vm.runInContext('reviewing', context), true);
  assert.equal(nodes.actions.children.some(n => n.textContent === 'Продолжить опрос'), false);
});
