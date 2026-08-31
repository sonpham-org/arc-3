"""q765 Vivarium Obligation -- follow fauna debt through thermal strata and reciprocal exchanges."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,VIVARIUM,GLASS,FAUNA,HEAT,IDENTITY,DEBT,GOAL,BAD=6,10,5,14,8,11,12,13,15
LEVELS=[{"name":"Borrowed Fauna","seq":(1,)},{"name":"Stratum Swap","seq":(2,1)},{"name":"Fair Return","seq":(3,1,2)},{"name":"Partner Memory","seq":(4,2,1,3)},{"name":"Delayed Trust","seq":(2,3,1,4,2,1)},{"name":"Vivarium Obligation","seq":(1,2,3,4,1,3,2,4,1)}]
def advance(s,a):
 identities,strata,debt,temp,trust,history,settled=s;ids=list(identities);pos=list(strata);d=list(debt)
 if a==1:i=ids[temp%3];d[i]+=1;pos[i]=(pos[i]+1+temp)%5;trust-=1;history=history+((i,1,temp),)
 elif a==2:ids[0],ids[1]=ids[1],ids[0];pos[0],pos[1]=pos[1],pos[0];temp=(temp+1)%5
 elif a==3:i=ids[(temp+1)%3];d[i]=max(0,d[i]-1);trust+=2;history=history+((i,-1,temp),)
 elif a==4:temp=(temp+2+int(trust>=0))%5;ids=ids[1:]+ids[:1]
 elif a==5:settled=(tuple(ids),tuple(pos),tuple(d),temp,trust,history[-5:])
 return tuple(ids),tuple(pos),tuple(d),temp,trust,history,settled
for x in LEVELS:
 s=((0,1,2),(0,2,4),(0,0,0),0,0,(),None)
 for a in x["seq"]:s=advance(s,a)
 x["plan"]=x["seq"]+(5,);x["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=VIVARIUM
  for lane,i in enumerate(g.identities):x=9+i*17;f[8:31,x:x+12]=GLASS;f[24-g.strata[i]*3:29,x+2:x+10]=FAUNA;f[10+g.temp*3:13+g.temp*3,x+2:x+10]=HEAT;f[8:11,x+4:x+8]=IDENTITY
  for i,d in enumerate(g.debt):x=9+i*17;f[36:42,x:x+12]=DEBT;f[43:46,x:x+2+d*3]=FAUNA
  lo=min(31,31+g.trust*4);hi=max(31,31+g.trust*4);f[55:59,max(6,lo):min(58,hi+1)]=IDENTITY
  if g.settled:f[51:58,49:57]=GOAL
  if g.bad:f[0:3,18:46]=BAD
  return f
class Q765(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"];ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q765",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.identities=(0,1,2);self.strata=(0,2,4);self.debt=(0,0,0);self.temp=self.trust=0;self.history=();self.settled=None
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.identities,self.strata,self.debt,self.temp,self.trust,self.history,self.settled=advance((self.identities,self.strata,self.debt,self.temp,self.trust,self.history,self.settled),a)
  elif a==6:
   if (self.identities,self.strata,self.debt,self.temp,self.trust,self.history,self.settled)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
