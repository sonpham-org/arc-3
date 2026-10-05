/* The lesson text is public research material; no learner data is collected. */
'use strict';
const el = id => document.getElementById(id);
let guide;
let current;
function text(id, value) { el(id).textContent = value; }
function showLevel() {
  const item = current.levels.find(level => level.level === Number(el('level').value));
  text('levelTip', item.tip);
  text('levelGap', item.gap);
}
function boardFigure(src, caption, alt, click) {
  const figure = document.createElement('figure');
  const wrap = document.createElement('div');
  wrap.className = 'board-wrap';
  const img = document.createElement('img');
  img.src = src; img.alt = alt; img.width = 384; img.height = 384; img.loading = 'lazy';
  wrap.append(img);
  if (click) {
    const mark = document.createElement('span');
    mark.className = 'click-mark'; mark.setAttribute('aria-hidden', 'true');
    mark.style.left = `${(click.x + .5) / 64 * 100}%`;
    mark.style.top = `${(click.y + .5) / 64 * 100}%`;
    wrap.append(mark);
  }
  const label = document.createElement('figcaption'); label.textContent = caption;
  figure.append(wrap, label);
  return figure;
}
function showGame(id) {
  current = guide.games.find(game => game.id === id) || guide.games.find(game => game.id === 'bp35');
  el('game').value = current.id;
  text('gameTitle', current.id.toUpperCase());
  text('goal', current.goal); text('trick', current.trick);
  el('playLink').href = `./#g=${encodeURIComponent(current.build)}`;
  el('board').src = current.picture;
  el('board').alt = current.picture_alt;
  text('boardCaption', `Starting picture for level ${current.practice_level}.`);
  text('practiceLevel', `A practice idea for level ${current.practice_level}. Try it and check what happens.`);
  el('steps').replaceChildren(...current.steps.map(step => {
    const li = document.createElement('li'); li.textContent = step; return li;
  }));
  text('mentorQuestion', current.mentor_question);
  text('limits', current.gap);
  el('sources').replaceChildren();
  for (const [effort, url] of Object.entries(current.replays)) {
    const a = document.createElement('a'); a.href = url; a.textContent = `${effort} replay`;
    el('sources').append(a, document.createTextNode(' · '));
  }
  el('sources').append(document.createTextNode(current.source_note));
  el('level').replaceChildren(...current.levels.map(level => {
    const option = document.createElement('option'); option.value = level.level; option.textContent = `Level ${level.level}`; return option;
  }));
  el('level').value = current.practice_level;
  showLevel();
  el('bp35Walkthrough').hidden = current.id !== 'bp35';
  el('lesson').hidden = false;
  history.replaceState(null, '', `#${current.id}`);
}
async function init() {
  try {
    const response = await fetch('./static/research/astra-learning-guide.json?v=20261005');
    if (!response.ok) throw new Error('Could not load the guide');
    guide = await response.json();
    el('game').replaceChildren(...guide.games.map(game => {
      const option = document.createElement('option'); option.value = game.id; option.textContent = game.id.toUpperCase(); return option;
    }));
    el('game').disabled = false;
    for (const scene of guide.bp35_walkthrough) {
      const card = document.createElement('section'); card.className = 'walk-card';
      const heading = document.createElement('h4'); heading.textContent = scene.title;
      const action = document.createElement('p'); action.textContent = scene.action;
      const boards = document.createElement('div'); boards.className = 'boards';
      boards.append(boardFigure(scene.before, 'Before', scene.before_alt, scene.click), boardFigure(scene.after, 'After', scene.after_alt));
      const result = document.createElement('p'); result.textContent = scene.result;
      const question = document.createElement('p'); question.className = 'question'; question.textContent = scene.question;
      const source = document.createElement('p'); source.className = 'small'; source.textContent = `Recorded move ${scene.step}. ${scene.limit || ''}`;
      card.append(heading, action, boards, result, question, source); el('walkthrough').append(card);
    }
    el('game').addEventListener('change', () => showGame(el('game').value));
    el('level').addEventListener('change', showLevel);
    window.addEventListener('hashchange', () => {
      const id = location.hash.slice(1).toLowerCase();
      if (guide.games.some(game => game.id === id)) showGame(id);
    });
    showGame(location.hash.slice(1).toLowerCase());
  } catch (error) { el('loadError').hidden = false; }
}
init();
