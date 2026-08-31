"""a028 Shared Pedal -- predict the lowest-pressure machine selected after every use."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,PLANT,MACHINE,PRESSURE,PEDAL,TARGET,VALVE,GOAL,BAD=7,10,14,11,6,12,8,13,15
LEVELS=[{"name":"Lowest Machine","seq":(1,)},{"name":"Target Reassigns","seq":(2,1)},{"name":"Pressure Record","seq":(3,1,2)},{"name":"Valve Cycle","seq":(4,2,1,3)},{"name":"Dynamic Recipient","seq":(2,3,1,4,2,1)},{"name":"Shared Pedal","seq":(1,2,3,4,1,3,2,4,1)}]
def advance(s,a):
 pressure,target,history,phase,balanced=s;p=list(pressure)
 if a==1:target=min(range(3),key=lambda i:(p[i],i));p[target]+=2+phase%2;history=history+((target,tuple(p),phase),)
 elif a==2:p[(target+1)%3]=max(0,p[(target+1)%3]-1);target=min(range(3),key=lambda i:(p[i],i))
 elif a==3:history=history+((target,tuple(p),phase),)
 elif a==4:phase=(phase+1)%4;p=[(v+phase)%7 for v in p];target=min(range(3),key=lambda i:(p[i],i))
 elif a==5:balanced=(tuple(p),target,history[-5:],phase)
 return tuple(p),target,history,phase,balanced
for x in LEVELS:
 s=((1,3,5),0,(),0,None)
 for a in x["seq"]:s=advance(s,a)
 x["plan"]=x["seq"]+(5,);x["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=PLANT
  for i,v in enumerate(g.pressure):x=8+i*18;f[8:31,x:x+13]=MACHINE;f[27-v*3:29,x+2:x+11]=PRESSURE;f[10:14,x+3:x+10]=TARGET if i==g.target else VALVE
  f[37:44,8:56]=PEDAL
  for i,(t,_,_) in enumerate(g.history[-3:]):f[48:53,8+i*14:18+i*14]=TARGET;f[54:57,8+i*14:10+i*14+t*2]=PRESSURE
  if g.balanced:f[51:58,49:57]=GOAL
  if g.bad:f[0:3,18:46]=BAD
  return f
class A028(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target_state=self.cfg["target"];ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("a028",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.pressure=(1,3,5);self.target=0;self.history=();self.phase=0;self.balanced=None
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target_state=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.pressure,self.target,self.history,self.phase,self.balanced=advance((self.pressure,self.target,self.history,self.phase,self.balanced),a)
  elif a==6:
   if (self.pressure,self.target,self.history,self.phase,self.balanced)==self.target_state:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
