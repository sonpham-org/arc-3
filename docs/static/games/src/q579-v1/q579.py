"""q579 Reedbed Counter -- shape a rival while every treatment rewires its route."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,WATER,TACTIC0,TACTIC1,TACTIC2,LINK,HISTORY,EXPLOIT,BAD=2,10,9,12,14,11,6,13,15
LEVELS=[
 {"name":"Paired Treatment","seq":(1,1)},{"name":"Split Treatment","seq":(1,2)},
 {"name":"Bridged Counter","seq":(2,1,5)},{"name":"Rewired Rival","seq":(1,2,1,2)},
 {"name":"Long Shaping","seq":(2,2,1,5,2)},{"name":"Reedbed Counter","seq":(1,2,2,1,5,2)}]
def shape(s,a):
 hist,links,function,rival,exploited=s;hist=list(hist)
 if a in (1,2):
  hist=(hist+[a-1])[-4:];links^=1<<((len(hist)+a)%4);function=(function+a)%5;rival=(sum(hist)+links.bit_count()+function)%3
 elif a==3:links>>=1;function=(function-1)%5;rival=(sum(hist)+links.bit_count()+function)%3
 elif a==5:links^=8;function=(function+2)%5;rival=(sum(hist)+links.bit_count()+function)%3
 return tuple(hist),links,function,rival,exploited
for x in LEVELS:
 s=((),0,0,0,None)
 for a in x["seq"]:s=shape(s,a)
 x["goal"],x["parity"]=s[3],s[1].bit_count()%2;x["plan"]=x["seq"]+(4,)
def advance(s,a,x):
 if a==4:
  if s[3]!=x["goal"] or s[1].bit_count()%2!=x["parity"]:return None
  return s[0],s[1],s[2],s[3],(s[3],s[1])
 return shape(s,a)
def target(x):
 s=((),0,0,0,None)
 for a in x["plan"]:s=advance(s,a,x);assert s is not None
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=WATER
  for i,c in enumerate((TACTIC0,TACTIC1,TACTIC2)):f[8:29,8+i*17:22+i*17]=c
  f[32:37,8+g.rival*17:22+g.rival*17]=EXPLOIT;f[41:45,8:8+g.links.bit_count()*11]=LINK;f[49:53,8:8+g.function*9]=HISTORY
  if g.exploited:f[55:60,39:56]=EXPLOIT
  if g.bad:f[0:3,18:46]=BAD
  return f
class Q579(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self.cfg=LEVELS[0];self._reset();self.target=target(self.cfg);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q579",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.hist=();self.links=self.function=self.rival=0;self.exploited=None
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=target(self.cfg)
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):
   s=advance((self.hist,self.links,self.function,self.rival,self.exploited),a,self.cfg)
   if s is None:self.bad=True;self.lose()
   else:self.hist,self.links,self.function,self.rival,self.exploited=s
  elif a==6:
   if (self.hist,self.links,self.function,self.rival,self.exploited)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
