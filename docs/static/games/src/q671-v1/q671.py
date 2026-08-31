"""q671 Pollen Analogy -- transfer a relation after its mapping visibly complements."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,MEADOW,SOURCE,TARGET,RELATION,WEAR,RULE,TRANSFER,BAD=4,14,11,9,12,13,6,10,15
LEVELS=[
 {"name":"Quarter Relation","ops":(1,),"wear":1},{"name":"Reflected Relation","ops":(1,2),"wear":1},
 {"name":"Delayed Transfer","ops":(1,1,2),"wear":2},{"name":"Worn Analogy","ops":(2,1,1,2),"wear":3},
 {"name":"Surface Change","ops":(1,2,1,1,2),"wear":4},{"name":"Pollen Analogy","ops":(2,1,2,1,1,2),"wear":5}]
def relation_after(ops):
 r=0
 for a in ops:r=(r+1)%4 if a==1 else (-r)%4
 return r
for x in LEVELS:
 r=relation_after(x["ops"]);rule=1;x["choice"]=(r%2)^rule;x["plan"]=x["ops"]+(3,)*x["wear"]+(4+x["choice"],)
def advance(s,a,x):
 relation,wear,rule,transferred=s
 if a==1:relation=(relation+1)%4
 elif a==2:relation=(-relation)%4
 elif a==3:
  wear+=1
  if wear==x["wear"]:rule^=1
 elif a in (4,5):
  choice=a-4
  if choice!=((relation%2)^rule):return None
  transferred=choice
 return relation,wear,rule,transferred
def target(x):
 s=(0,0,0,None)
 for a in x["plan"]:s=advance(s,a,x);assert s is not None
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=MEADOW;f[8:34,8:29]=SOURCE;f[8:34,35:56]=TARGET
  for i in range(4):f[12+i*5:15+i*5,11:26]=RELATION+i%2
  f[12+g.relation*5:15+g.relation*5,38:53]=TRANSFER;f[40:44,8:8+min(g.wear,6)*8]=WEAR;f[49:54,8:28]=RULE+g.rule
  if g.transferred is not None:f[54:59,39:56]=TRANSFER+g.transferred
  if g.bad:f[0:3,18:46]=BAD
  return f
class Q671(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self.cfg=LEVELS[0];self._reset();self.target=target(self.cfg);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q671",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.relation=self.wear=self.rule=0;self.transferred=None
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=target(self.cfg)
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):
   s=advance((self.relation,self.wear,self.rule,self.transferred),a,self.cfg)
   if s is None:self.bad=True;self.lose()
   else:self.relation,self.wear,self.rule,self.transferred=s
  elif a==6:
   if (self.relation,self.wear,self.rule,self.transferred)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
