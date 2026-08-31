"""q673 Impeller Analogy -- transfer direction and blade gap across unlike surfaces."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,FIELD,SOURCE,BLADE,TARGET,RIDER,WAKE,SURFACE,COST,GOAL,BAD=5,11,12,10,14,6,9,7,4,13,15
LEVELS=[
 {"name":"One Rotation","relation":(0,2),"ops":(1,),"surface":0},
 {"name":"Changed Surface","relation":(1,3),"ops":(2,),"surface":1},
 {"name":"Counter Rotation","relation":(0,4),"ops":(1,2),"surface":1},
 {"name":"Blade Relation","relation":(2,3),"ops":(1,1,2),"surface":2},
 {"name":"Sampled Transfer","relation":(1,4),"ops":(2,1,2,1),"surface":2},
 {"name":"Impeller Analogy","relation":(0,5),"ops":(1,2,2,1,2),"surface":1}]
def advance(s,a):
 relation,wake,mapped,surface,cost,done=s;direction,gap=relation
 if a==1:direction^=1;wake=(wake+1)%4
 elif a==2:gap=1+gap%5;direction^=wake%2;wake=(wake+1)%4
 elif a==3:mapped=(direction,gap,wake%2);cost+=2 if mapped==s[2] and mapped is not None else 1
 elif a==4:surface=(surface+1)%3
 elif a==5:
  if mapped is None:return None
  done=(mapped,surface,cost)
 return (direction,gap),wake,mapped,surface,cost,done
for x in LEVELS:x["plan"]=x["ops"]+(3,)+(4,)*x["surface"]+(5,)
def target(x):
 s=(x["relation"],0,None,0,0,None)
 for a in x["plan"]:s=advance(s,a);assert s is not None
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=FIELD;f[8:34,7:29]=SOURCE;f[8:34,35:57]=TARGET
  direction,gap=g.relation
  for i in range(6):
   f[12+(i%3)*7:17+(i%3)*7,10+(i//3)*10:15+(i//3)*10]=BLADE if i in (direction,gap%6) else WAKE
   f[12+(i%3)*7:17+(i%3)*7,38+(i//3)*10:43+(i//3)*10]=RIDER if g.mapped and i in g.mapped else SURFACE
  f[39:43,8:8+g.wake*11+8]=WAKE;f[47:51,8:8+g.surface*15+10]=SURFACE;f[53:57,8:8+min(g.cost,9)*5]=COST
  if g.done:f[55:59,43:56]=GOAL
  if g.bad:f[0:3,18:46]=BAD
  return f
class Q673(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self.cfg=LEVELS[0];self._reset();self.target=target(self.cfg);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q673",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.relation=self.cfg["relation"];self.wake=self.surface=self.cost=0;self.mapped=self.done=None
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=target(self.cfg)
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):
   s=advance((self.relation,self.wake,self.mapped,self.surface,self.cost,self.done),a)
   if s is None:self.bad=True;self.lose()
   else:self.relation,self.wake,self.mapped,self.surface,self.cost,self.done=s
  elif a==6:
   if (self.relation,self.wake,self.mapped,self.surface,self.cost,self.done)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
