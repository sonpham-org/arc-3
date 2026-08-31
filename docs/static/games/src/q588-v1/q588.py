"""q588 Escapement Counter -- diagnose a clockwork rival before exploiting its tactic."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,TOWER,GEAR,WEIGHT,PHASE,RIVAL,CLUE,GOAL,BAD=2,11,7,14,9,12,6,13,15
LEVELS=[{"name":"First Tactic","seq":(1,)},{"name":"Nested Phase","seq":(2,1)},{"name":"Diagnostic Tap","seq":(3,1,2)},{"name":"False Fault","seq":(4,3,2,1)},{"name":"Shape The Clock","seq":(2,3,1,4,2,3)},{"name":"Escapement Counter","seq":(3,1,4,2,3,2,1,4,3)}]
def advance(s,a):
 recent,tactic,phase,weights,clues,fault,exploit=s;v=list(weights)
 if a in (1,2):recent=(recent+(a,))[-3:];i=(tactic+phase+a)%3;v[i]=(v[i]+a+phase)%6;phase=(phase+a)%5;tactic=(sum(recent)+phase+sum(v))%3
 elif a==3:fault=(phase+tactic+v[tactic])%3;clues=clues+((phase,tactic,fault),);phase=(phase+1)%5
 elif a==4:v[0],v[2]=v[2],v[0];phase=(phase+2)%5;tactic=(tactic+fault+1)%3
 elif a==5:exploit=(recent,tactic,phase,tuple(v),clues[-3:],fault)
 return recent,tactic,phase,tuple(v),clues,fault,exploit
for x in LEVELS:
 s=((),0,0,(1,2,3),(),0,None)
 for a in x["seq"]:s=advance(s,a)
 x["plan"]=x["seq"]+(5,);x["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=TOWER
  for i,v in enumerate(g.weights):x=8+i*18;f[8+i*3:27,x:x+12]=GEAR;f[22-v*2:29,x+3:x+9]=WEIGHT;f[10:14,x+4:x+8]=RIVAL if i==g.tactic else PHASE
  for i,(_,t,z) in enumerate(g.clues[-4:]):x=8+i*12;f[35:42,x:x+9]=CLUE;f[43:46,x:x+3+t*2]=RIVAL;f[47:49,x:x+2+z*2]=PHASE
  f[52:56,8:8+g.phase*10+8]=PHASE
  if g.exploit:f[51:58,49:57]=GOAL
  if g.bad:f[0:3,18:46]=BAD
  return f
class Q588(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"];ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q588",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.recent=();self.tactic=self.phase=self.fault=0;self.weights=(1,2,3);self.clues=();self.exploit=None
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.recent,self.tactic,self.phase,self.weights,self.clues,self.fault,self.exploit=advance((self.recent,self.tactic,self.phase,self.weights,self.clues,self.fault,self.exploit),a)
  elif a==6:
   if (self.recent,self.tactic,self.phase,self.weights,self.clues,self.fault,self.exploit)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
