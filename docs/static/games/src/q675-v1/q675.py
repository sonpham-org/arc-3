"""q675 Vivarium Analogy -- transfer a temperature relation through a reciprocal partner policy."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,FIELD,SOURCE,STRATUM,TARGET,FAUNA,FAIR,UNFAIR,GOAL,BAD=5,11,12,10,14,6,9,7,13,15
LEVELS=[
 {"name":"One Exchange","relation":(0,2),"ops":(1,),"surface":0},
 {"name":"Changed Surface","relation":(1,3),"ops":(2,),"surface":1},
 {"name":"Reciprocal Pair","relation":(0,4),"ops":(1,2),"surface":1},
 {"name":"Fair Transfer","relation":(2,3),"ops":(1,1,2),"surface":2},
 {"name":"Partner Memory","relation":(1,4),"ops":(2,1,2,1),"surface":2},
 {"name":"Vivarium Analogy","relation":(0,5),"ops":(1,2,2,1,2),"surface":1}]
def advance(s,a):
 relation,fairness,mapped,surface,done=s;temp,gap=relation
 if a==1:temp=(temp+1)%3;fairness+=1
 elif a==2:gap=1+gap%5;fairness-=1 if temp%2 else 0
 elif a==3:mapped=(temp,gap,int(fairness>=0))
 elif a==4:surface=(surface+1)%3
 elif a==5:
  if mapped is None:return None
  done=(mapped,surface,fairness)
 return (temp,gap),fairness,mapped,surface,done
for x in LEVELS:x["plan"]=x["ops"]+(3,)+(4,)*x["surface"]+(5,)
def target(x):
 s=(x["relation"],0,None,0,None)
 for a in x["plan"]:s=advance(s,a);assert s is not None
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=FIELD;f[8:34,7:29]=SOURCE;f[8:34,35:57]=TARGET
  temp,gap=g.relation
  for i in range(6):
   f[12+(i%3)*7:17+(i%3)*7,10+(i//3)*10:15+(i//3)*10]=STRATUM if i in (temp,gap%6) else FAIR
   f[12+(i%3)*7:17+(i%3)*7,38+(i//3)*10:43+(i//3)*10]=FAUNA if g.mapped and i in g.mapped else UNFAIR
  f[39:43,8:28]=FAIR if g.fairness>=0 else UNFAIR;f[47:51,8:8+g.surface*15+10]=STRATUM
  if g.done:f[55:59,43:56]=GOAL
  if g.bad:f[0:3,18:46]=BAD
  return f
class Q675(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self.cfg=LEVELS[0];self._reset();self.target=target(self.cfg);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q675",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.relation=self.cfg["relation"];self.fairness=self.surface=0;self.mapped=self.done=None
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=target(self.cfg)
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):
   s=advance((self.relation,self.fairness,self.mapped,self.surface,self.done),a)
   if s is None:self.bad=True;self.lose()
   else:self.relation,self.fairness,self.mapped,self.surface,self.done=s
  elif a==6:
   if (self.relation,self.fairness,self.mapped,self.surface,self.done)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
