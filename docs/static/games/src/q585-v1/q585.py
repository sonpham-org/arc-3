"""q585 Vivarium Counter -- shape an adaptive keeper through legible reciprocity."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,HABITAT,GLASS,FAUNA,HEAT,KEEPER,HISTORY,GOAL,BAD=1,10,5,14,8,12,6,13,15
LEVELS=[{"name":"Keeper Watches","seq":(1,)},{"name":"Warm Response","seq":(2,1)},{"name":"Fair Exchange","seq":(3,1,2)},{"name":"Changed Tactic","seq":(1,4,2,3)},{"name":"Shape The Keeper","seq":(2,3,1,4,2,1)},{"name":"Vivarium Counter","seq":(3,1,2,4,1,3,2,1,4)}]
def advance(s,a):
 recent,keeper,fauna,stratum,fairness,offer,exploit=s;v=list(fauna)
 if a in (1,2):recent=(recent+(a,))[-3:];i=(keeper+a+stratum)%3;v[i]=(v[i]+a+fairness)%5;fairness=max(-3,min(5,fairness+(1 if a==1 else -1)));keeper=(sum(recent)+fairness+stratum)%3
 elif a==3:offer=(keeper,tuple(v),fairness);fairness+=1 if fairness>=0 else -1;stratum=(stratum+1)%4
 elif a==4:v=v[1:]+v[:1];stratum=(stratum+2)%4;keeper=(keeper+stratum+int(fairness<0))%3
 elif a==5:exploit=(recent,keeper,tuple(v),stratum,fairness,offer)
 return recent,keeper,tuple(v),stratum,fairness,offer,exploit
for x in LEVELS:
 s=((),0,(0,1,2),0,0,None,None)
 for a in x["seq"]:s=advance(s,a)
 x["plan"]=x["seq"]+(5,);x["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=HABITAT;f[7:34,7:57]=GLASS
  for i,v in enumerate(g.fauna):x=10+i*16;f[24-v*3:30,x:x+10]=FAUNA;f[10+i*3:13+i*3,x:x+10]=HEAT if i==g.keeper else KEEPER
  for i,a in enumerate(g.recent):x=9+i*15;f[37:43,x:x+11]=HISTORY;f[39:41,x:x+3+a*3]=FAUNA
  f[48:53,8:8+g.stratum*12+8]=HEAT;lo=min(31,31+g.fairness*4);hi=max(31,31+g.fairness*4);f[55:59,max(6,lo):min(58,hi+1)]=KEEPER
  if g.exploit:f[51:58,49:57]=GOAL
  if g.bad:f[0:3,18:46]=BAD
  return f
class Q585(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"];ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q585",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.recent=();self.keeper=0;self.fauna=(0,1,2);self.stratum=self.fairness=0;self.offer=self.exploit=None
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.recent,self.keeper,self.fauna,self.stratum,self.fairness,self.offer,self.exploit=advance((self.recent,self.keeper,self.fauna,self.stratum,self.fairness,self.offer,self.exploit),a)
  elif a==6:
   if (self.recent,self.keeper,self.fauna,self.stratum,self.fairness,self.offer,self.exploit)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
