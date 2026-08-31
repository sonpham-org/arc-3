"""q795 Vivarium Rhythm -- interrupt two temperature clocks under a reciprocal partner policy."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,TERRARIUM,FAUNA,TEMP,FAST,SLOW,FAIR,GOAL,BAD=9,1,14,10,6,12,11,13,15
LEVELS=[
 {"name":"Fauna Tick","seq":(1,)},{"name":"Temperature Cycle","seq":(1,1,2)},
 {"name":"Fairness Pulse","seq":(3,1,2,1)},{"name":"Partner Window","seq":(1,2,1,3,2)},
 {"name":"Reciprocal Macro","seq":(2,1,3,1,2,1,1)},
 {"name":"Vivarium Rhythm","seq":(1,2,3,1,1,2,1,3,2,1,1)}]
def advance(s,a):
 fast,slow,temp,fairness,partner,ticks,interrupted=s
 if a==1:
  fast=(fast+1)%4;ticks+=1;temp=(temp+1+partner)%6;fairness+=1 if temp%2==0 else -1
  if fast==0:slow=(slow+1)%5
 elif a==2:fast=(fast+2)%4;slow=(slow+1)%5;temp=(temp+2)%6;ticks+=2
 elif a==3:partner=int(fairness>=0);fairness=-fairness+partner
 elif a==4:fast=slow=temp=0;ticks+=1
 elif a==5:interrupted=(fast,slow,temp,fairness,partner,ticks)
 return fast,slow,temp,fairness,partner,ticks,interrupted
for x in LEVELS:
 s=(0,0,0,0,0,0,None)
 for a in x["seq"]:s=advance(s,a)
 x["plan"]=x["seq"]+(5,);x["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=TERRARIUM
  for i in range(12):x=7+(i%6)*9;y=8+(i//6)*15;f[y:y+11,x:x+7]=TEMP;f[y+3:y+8,x+2:x+5]=FAUNA if i in (g.temp,g.partner+6) else FAIR
  f[40:44,8:8+g.fast*12+8]=FAST;f[47:51,8:8+g.slow*9+7]=SLOW
  center=31;lo=max(8,min(center,center+g.fairness));hi=min(55,max(center,center+g.fairness));f[54:58,lo:hi+1]=FAIR
  if g.interrupted:f[52:58,49:57]=GOAL
  if g.bad:f[0:3,18:46]=BAD
  return f
class Q795(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"]
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q795",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.fast=self.slow=self.temp=self.fairness=self.partner=self.ticks=0;self.interrupted=None
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.fast,self.slow,self.temp,self.fairness,self.partner,self.ticks,self.interrupted=advance((self.fast,self.slow,self.temp,self.fairness,self.partner,self.ticks,self.interrupted),a)
  elif a==6:
   if (self.fast,self.slow,self.temp,self.fairness,self.partner,self.ticks,self.interrupted)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
