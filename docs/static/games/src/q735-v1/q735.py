"""q735 Vivarium Gradient -- route conserved microfauna under thermal capacity and reciprocity."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,VIVARIUM,GLASS,FAUNA,HEAT,MASS,TRUST,GOAL,BAD=4,10,5,14,8,6,12,13,15
LEVELS=[{"name":"Fauna Flow","seq":(1,)},{"name":"Thermal Capacity","seq":(2,1)},{"name":"Fair Exchange","seq":(3,1,2)},{"name":"Stratum Shift","seq":(4,2,1,3)},{"name":"Reciprocal Route","seq":(2,3,1,4,2,1)},{"name":"Vivarium Gradient","seq":(1,2,3,4,1,3,2,4,1)}]
def advance(s,a):
 mass,temp,capacity,trust,history,commit=s;v=list(mass)
 if a==1:d=min(v[0],capacity[0]+max(0,trust));v[0]-=d;v[1]+=d;trust=min(4,trust+1)
 elif a==2:d=min(v[1],capacity[1]+max(0,-trust));v[1]-=d;v[2]+=d;trust=max(-3,trust-1)
 elif a==3:history=history+((tuple(v),temp,trust),);temp=(temp+1+int(trust>=0))%5
 elif a==4:capacity=capacity[1:]+capacity[:1];temp=(temp+2)%5;v=v[1:]+v[:1]
 elif a==5:commit=(tuple(v),temp,tuple(capacity),trust,history[-3:],sum(v))
 return tuple(v),temp,tuple(capacity),trust,history,commit
for x in LEVELS:
 s=((8,0,0),0,(1,2,3),0,(),None)
 for a in x["seq"]:s=advance(s,a)
 x["plan"]=x["seq"]+(5,);x["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=VIVARIUM
  for i,v in enumerate(g.mass):x=8+i*18;f[8:31,x:x+13]=GLASS;f[27-v*2:29,x+2:x+11]=MASS;f[10+g.temp*3:13+g.temp*3,x+2:x+11]=HEAT
  for i,c in enumerate(g.capacity):x=9+i*17;f[35:41,x:x+12]=FAUNA;f[42:45,x:x+2+c*3]=HEAT
  for i,_ in enumerate(g.history[-3:]):f[48:52,8+i*14:18+i*14]=TRUST
  lo=min(31,31+g.trust*4);hi=max(31,31+g.trust*4);f[55:59,max(6,lo):min(58,hi+1)]=TRUST
  if g.commit:f[51:58,49:57]=GOAL
  if g.bad:f[0:3,18:46]=BAD
  return f
class Q735(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"];ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q735",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.mass=(8,0,0);self.temp=0;self.capacity=(1,2,3);self.trust=0;self.history=();self.commit=None
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.mass,self.temp,self.capacity,self.trust,self.history,self.commit=advance((self.mass,self.temp,self.capacity,self.trust,self.history,self.commit),a)
  elif a==6:
   if (self.mass,self.temp,self.capacity,self.trust,self.history,self.commit)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
