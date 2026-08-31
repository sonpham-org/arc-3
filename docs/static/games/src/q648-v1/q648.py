"""q648 Escapement Sandbox -- reset clockwork trials while preserving diagnostic evidence."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay

BG,LAB,GEAR,WEIGHT,TRIAL,EVIDENCE,RESET,GOAL,BAD=4,10,12,14,6,9,11,13,15
LEVELS=[
 {"name":"First Trial","seq":(1,3)},{"name":"Reversible Gear","seq":(2,3,4)},
 {"name":"Persistent Evidence","seq":(1,3,4,2,3)},{"name":"Exclusive Outcome","seq":(2,1,3,4,1,3)},
 {"name":"Two Hypotheses","seq":(1,2,3,4,2,2,3)},
 {"name":"Escapement Sandbox","seq":(2,1,3,4,1,2,3,4,2,3)}]
def advance(s,a):
 physical,phase,evidence,trials,commit=s
 if a==1:physical=(physical+1+phase)%5;phase=(phase+1)%4
 elif a==2:physical=(2*physical+phase+1)%5;phase=(phase+2)%4
 elif a==3:evidence=evidence+((physical,phase),);trials+=1
 elif a==4:physical=phase=0
 elif a==5:commit=(physical,phase,evidence[-4:],trials)
 return physical,phase,evidence,trials,commit
for x in LEVELS:
 s=(0,0,(),0,None)
 for a in x["seq"]:s=advance(s,a)
 x["plan"]=x["seq"]+(5,);x["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=LAB;f[8:31,7:29]=TRIAL;f[8:31,35:57]=RESET
  for i in range(5):f[13+i%2*9:20+i%2*9,10+(i//2)*6:15+(i//2)*6]=GEAR if i==g.physical else WEIGHT
  for i,(p,h) in enumerate(g.evidence[-6:]):
   x=8+i*8;f[36:42,x:x+6]=EVIDENCE;f[43:46,x:x+2+p]=GEAR;f[47:49,x:x+2+h]=WEIGHT
  f[52:56,8:8+g.phase*11+7]=RESET
  if g.commit:f[52:58,49:57]=GOAL
  if g.bad:f[0:3,18:46]=BAD
  return f
class Q648(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"]
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q648",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.physical=self.phase=self.trials=0;self.evidence=();self.commit=None
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.physical,self.phase,self.evidence,self.trials,self.commit=advance((self.physical,self.phase,self.evidence,self.trials,self.commit),a)
  elif a==6:
   if (self.physical,self.phase,self.evidence,self.trials,self.commit)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
