"""q665 Waystation Analogy -- transfer a shifting corridor relation to supply walkers."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,SAND,SOURCE,PATH,TARGET,WALKER,SURFACE,HISTORY,GOAL,BAD=5,11,12,10,14,6,7,9,13,15
LEVELS=[
 {"name":"Rotated Route","path":(0,1,2),"ops":(1,),"surface":0},
 {"name":"Changed Cargo","path":(0,2,1),"ops":(2,),"surface":1},
 {"name":"Two Transforms","path":(1,0,2),"ops":(1,2),"surface":1},
 {"name":"Recent Relation","path":(2,0,1),"ops":(1,1,2),"surface":2},
 {"name":"Countered Transfer","path":(1,2,0),"ops":(2,1,2,2),"surface":2},
 {"name":"Waystation Analogy","path":(0,2,1),"ops":(1,2,1,1,2),"surface":1}]
def advance(s,a):
 path,shift,history,mapped,surface,done=s;path=list(path)
 if a in (1,2):
  op=a-1;history=(history+(op,))[-2:]
  if a==1:path=path[1:]+path[:1]
  else:path=[2-v for v in reversed(path)]
  if len(history)==2 and history[0]==history[1]:shift=(shift+1)%3;path=[(v+shift)%3 for v in path]
 elif a==3:mapped=(tuple((path[i+1]-path[i])%3 for i in range(2)),shift)
 elif a==4:surface=(surface+1)%3
 elif a==5:
  if mapped is None:return None
  done=(mapped,surface,tuple(history))
 return tuple(path),shift,history,mapped,surface,done
for x in LEVELS:x["plan"]=x["ops"]+(3,)+(4,)*x["surface"]+(5,)
def target(x):
 s=(x["path"],0,(),None,0,None)
 for a in x["plan"]:s=advance(s,a);assert s is not None
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=SAND;f[8:34,7:29]=SOURCE;f[8:34,35:57]=TARGET
  for i,v in enumerate(g.path):f[12+i*7,10+v*6:16+v*6]=PATH;f[12+i*7,38+v*6:44+v*6]=WALKER if g.mapped else SURFACE
  f[39:43,8:8+g.shift*15+10]=HISTORY
  for i,v in enumerate(g.history):f[47:52,8+i*13:18+i*13]=PATH if v else WALKER
  f[54:58,32:32+g.surface*7+6]=SURFACE
  if g.done:f[55:59,8:27]=GOAL
  if g.bad:f[0:3,18:46]=BAD
  return f
class Q665(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self.cfg=LEVELS[0];self._reset();self.target=target(self.cfg);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q665",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.path=self.cfg["path"];self.shift=self.surface=0;self.history=();self.mapped=self.done=None
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=target(self.cfg)
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):
   s=advance((self.path,self.shift,self.history,self.mapped,self.surface,self.done),a)
   if s is None:self.bad=True;self.lose()
   else:self.path,self.shift,self.history,self.mapped,self.surface,self.done=s
  elif a==6:
   if (self.path,self.shift,self.history,self.mapped,self.surface,self.done)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
