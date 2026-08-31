"""q581 Pollen Counter -- shape a rival whose update law changes at visible wear."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,MEADOW,LANE,TACTIC,HISTORY,WEAR,RULE,EXPLOIT,BAD=1,14,10,12,8,13,6,11,15
LEVELS=[
 {"name":"Paired Tactics","seq":(1,1),"wear":5},{"name":"Split Tactics","seq":(1,2),"wear":5},
 {"name":"Wear Counter","seq":(2,1,2),"wear":2},{"name":"Alternating Rival","seq":(1,2,1,2),"wear":3},
 {"name":"Long Shaping","seq":(2,2,1,2,1),"wear":3},{"name":"Pollen Counter","seq":(1,2,2,1,2,1),"wear":4}]
def shaped(seq,threshold):
 hist=[];rule=wear=rival=0
 for a in seq:
  hist=(hist+[a-1])[-2:];wear+=1
  if wear==threshold:rule^=1
  if len(hist)==2:rival=(hist[-2]+2*hist[-1]+rule)%3
 return rival
for x in LEVELS:x["goal"]=shaped(x["seq"],x["wear"]);x["plan"]=x["seq"]+(4,)
def advance(s,a,x):
 hist,rule,wear,rival,exploited=s;hist=list(hist)
 if a in (1,2):
  hist=(hist+[a-1])[-2:];wear+=1
  if wear==x["wear"]:rule^=1
  if len(hist)==2:rival=(hist[-2]+2*hist[-1]+rule)%3
 elif a==3:hist=[]
 elif a==4:
  if len(hist)<2 or rival!=x["goal"]:return None
  exploited=rival
 elif a==5:rival=(rival+1)%3
 return tuple(hist),rule,wear,rival,exploited
def target(x):
 s=((),0,0,0,None)
 for a in x["plan"]:s=advance(s,a,x);assert s is not None
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=MEADOW
  for i in range(3):f[8:29,8+i*17:22+i*17]=LANE+i
  f[33:39,8+g.rival*17:22+g.rival*17]=TACTIC;f[43:47,8:8+min(g.wear,6)*8]=WEAR;f[50:54,8:28]=RULE+g.rule
  for i,v in enumerate(g.hist):f[56:60,38+i*9:45+i*9]=HISTORY+v
  if g.exploited is not None:f[31:58,56:59]=EXPLOIT
  if g.bad:f[0:3,18:46]=BAD
  return f
class Q581(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self.cfg=LEVELS[0];self._reset();self.target=target(self.cfg);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q581",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.hist=();self.rule=self.wear=self.rival=0;self.exploited=None
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=target(self.cfg)
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):
   s=advance((self.hist,self.rule,self.wear,self.rival,self.exploited),a,self.cfg)
   if s is None:self.bad=True;self.lose()
   else:self.hist,self.rule,self.wear,self.rival,self.exploited=s
  elif a==6:
   if (self.hist,self.rule,self.wear,self.rival,self.exploited)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
