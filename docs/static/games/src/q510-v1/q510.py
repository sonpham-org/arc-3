"""q510 Spore Frame -- align two autonomous greenhouse schedules in a moving frame."""
from copy import deepcopy
from math import lcm
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,GREENHOUSE,HUMIDITY,SPORE,FRAME,PHASEA,PHASEB,CONTACT,BAD=9,10,12,14,5,11,6,7,15
def routine(n):return tuple((i%4)+1 for i in range(n))+(5,)
LEVELS=[{"name":"Shared Pulse","periods":(2,2),"plan":routine(2)},{"name":"Triple Bloom","periods":(3,3),"plan":routine(3)},{"name":"Nested Cycle","periods":(2,4),"plan":routine(4)},{"name":"Sparse Meeting","periods":(2,3),"plan":routine(6)},{"name":"Long Confluence","periods":(3,4),"plan":routine(12)},{"name":"Spore Frame","periods":(4,5),"plan":routine(20)}]
def advance(s,a,x):
 colonies,rotation,offset,pa,pb,contacts,history=s;colonies=list(colonies);history=list(history)
 if a in (1,2,3,4):
  if a==1:colonies[0]=(colonies[0]+1+offset)%8
  elif a==2:colonies[1]=(colonies[1]+1+rotation)%8
  elif a==3:rotation=(rotation+1)%4
  elif a==4:offset=(offset+1)%4
  history.append((a,rotation,offset));pa=(pa+1)%x["periods"][0];pb=(pb+1)%x["periods"][1]
 elif a==5:
  if pa or pb or not history:return None
  contacts+=1;colonies=[(colonies[0]+rotation)%8,(colonies[1]+offset)%8];history=[]
 return tuple(colonies),rotation,offset,pa,pb,contacts,tuple(history)
def target(x):
 s=((1,5),0,0,0,0,0,())
 for a in x["plan"]:s=advance(s,a,x);assert s is not None
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=GREENHOUSE
  f[8:33,7:29]=HUMIDITY;f[8:33,35:57]=FRAME
  for i,v in enumerate(g.colonies):x=10+i*28;f[11+v*2:17+v*2,x:x+14]=SPORE-i
  f[37:40,8:11+g.pa*9]=PHASEA;f[43:46,8:11+g.pb*9]=PHASEB;f[50:53,8:11+g.rotation*11]=FRAME;f[55:58,8:11+g.offset*11]=CONTACT
  if g.bad:f[61:64,20:44]=BAD
  return f
class Q510(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self._reset();self.target=target(LEVELS[0]);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q510",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.colonies=(1,5);self.rotation=self.offset=self.pa=self.pb=self.contacts=0;self.history=()
 def on_set_level(self,l):self._reset();self.bad=False;self.target=target(LEVELS[self.level_index])
 def step(self):
  a=self.action.id.value;x=LEVELS[self.level_index]
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):
   s=advance((self.colonies,self.rotation,self.offset,self.pa,self.pb,self.contacts,self.history),a,x)
   if s is None:self.bad=True;self.lose()
   else:self.colonies,self.rotation,self.offset,self.pa,self.pb,self.contacts,self.history=s
  elif a==6:
   if (self.colonies,self.rotation,self.offset,self.pa,self.pb,self.contacts,self.history)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
