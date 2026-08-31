"""q599 Strata Grammar -- decode a composed message after its physical probe is undone."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,QUARRY,FAULT,GLYPH,GROUP,RELATION,KNOWLEDGE,DECODE,BAD=10,8,11,6,2,9,4,13,15
LEVELS=[
 {"name":"Probe the Group","plan":(1,3,4,5)},{"name":"Probe the Relation","plan":(2,3,4,5)},
 {"name":"Composed Probe","plan":(1,2,3,4,5)},{"name":"Repeated Reading","plan":(1,3,4,2,3,4,5)},
 {"name":"Persistent Syntax","plan":(1,2,3,4,1,3,4,5)},{"name":"Strata Grammar","plan":(2,3,4,1,2,3,4,1,5)}]
def advance(s,a,x):
 group,relation,world,knowledge,trace,decoded=s
 if a==1:group=(group+1)%4
 elif a==2:relation=(relation+1)%3
 elif a==3:world=(group+relation+trace+1)%5;knowledge|=1<<world;trace=(trace+world+1)%6
 elif a==4:world=0
 elif a==5:
  if not knowledge:return None
  decoded=(group,relation,knowledge,trace)
 return group,relation,world,knowledge,trace,decoded
def target(x):
 s=(0,0,0,0,0,None)
 for a in x["plan"]:s=advance(s,a,x);assert s is not None
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=QUARRY
  for i in range(4):f[8+i*9:14+i*9,8:56]=FAULT+i%2
  f[10:14,9:13+g.group*8]=GROUP;f[19:23,9:13+g.relation*11]=RELATION;f[28:32,9:13+g.trace*7]=GLYPH
  f[44:48,8:8+g.world*10]=GLYPH;f[51:54,8:8+g.knowledge.bit_count()*8]=KNOWLEDGE
  if g.decoded:f[55:59,39:56]=DECODE
  if g.bad:f[0:3,18:46]=BAD
  return f
class Q599(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self.cfg=LEVELS[0];self._reset();self.target=target(self.cfg);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q599",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.group=self.relation=self.world=self.knowledge=self.trace=0;self.decoded=None
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=target(self.cfg)
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):
   s=advance((self.group,self.relation,self.world,self.knowledge,self.trace,self.decoded),a,self.cfg)
   if s is None:self.bad=True;self.lose()
   else:self.group,self.relation,self.world,self.knowledge,self.trace,self.decoded=s
  elif a==6:
   if (self.group,self.relation,self.world,self.knowledge,self.trace,self.decoded)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
