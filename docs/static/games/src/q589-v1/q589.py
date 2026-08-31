"""q589 Monsoon Counter -- shape a rival at unequal weather-clock phase pairs."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,GARDEN,RAIN,STORM,FAST,SLOW,RIVAL,GOAL,BAD=2,10,14,9,6,12,11,13,15
LEVELS=[
 {"name":"First Tactic","seq":(1,)},{"name":"Second Clock","seq":(2,1)},
 {"name":"Storm Treatment","seq":(3,1,2)},{"name":"Phase Counter","seq":(1,4,2,3)},
 {"name":"Shape The Cell","seq":(2,3,1,4,2,1)},
 {"name":"Monsoon Counter","seq":(3,1,2,4,1,3,2,1,4)}]
def advance(s,a):
 recent,rival,fast,slow,storm,exploit=s
 if a in (1,2):recent=(recent+(a,))[-2:];fast=(fast+a)%4;slow=(slow+int(fast==0)+a-1)%5;rival=(sum(recent)+fast+slow+storm)%3
 elif a==3:storm=(storm+1+rival)%6;fast=(fast+1)%4
 elif a==4:slow=(slow+2)%5;storm=(storm+slow)%6;rival=(rival+storm)%3
 elif a==5:exploit=(recent,rival,fast,slow,storm)
 return recent,rival,fast,slow,storm,exploit
for x in LEVELS:
 s=((),0,0,0,0,None)
 for a in x["seq"]:s=advance(s,a)
 x["plan"]=x["seq"]+(5,);x["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=GARDEN
  for i in range(12):x=7+(i%6)*9;y=8+(i//6)*14;f[y:y+10,x:x+7]=STORM;f[y+3:y+7,x+2:x+5]=RAIN if i==g.storm%12 else FAST
  for i,a in enumerate(g.recent):f[38:44,9+i*20:23+i*20]=RIVAL;f[40:42,12+i*20:12+i*20+a*4]=RAIN
  f[48:52,8:8+g.fast*12+8]=FAST;f[54:58,8:8+g.slow*9+7]=SLOW
  if g.exploit:f[52:58,49:57]=GOAL
  if g.bad:f[0:3,18:46]=BAD
  return f
class Q589(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"]
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q589",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.recent=();self.rival=self.fast=self.slow=self.storm=0;self.exploit=None
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.recent,self.rival,self.fast,self.slow,self.storm,self.exploit=advance((self.recent,self.rival,self.fast,self.slow,self.storm,self.exploit),a)
  elif a==6:
   if (self.recent,self.rival,self.fast,self.slow,self.storm,self.exploit)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
