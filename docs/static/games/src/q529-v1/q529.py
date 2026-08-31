"""q529 Monsoon Frame -- compose local rain motion with a global dual-cycle weather frame."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,GARDEN,CLOUD,RAIN,FRAME,CYCLEA,CYCLEB,EXCHANGE,BAD=9,10,12,14,5,11,6,7,15
def routine(n):return tuple((i%4)+1 for i in range(n))+(5,)
LEVELS=[{"name":"Paired Frame","periods":(2,2),"plan":routine(2)},{"name":"Triple Frame","periods":(3,3),"plan":routine(3)},{"name":"Nested Frame","periods":(2,4),"plan":routine(4)},{"name":"Unequal Frame","periods":(2,3),"plan":routine(6)},{"name":"Long Alignment","periods":(3,4),"plan":routine(12)},{"name":"Monsoon Frame","periods":(4,5),"plan":routine(20)}]
def advance(s,a,x):
 shuttles,rotation,offset,pa,pb,history,exchange=s;shuttles=list(shuttles);history=list(history)
 if a in (1,2,3,4):
  if a in (1,2):
   i=a-1;direction=(rotation+(1 if i else -1))%4;shuttles[i]=(shuttles[i]+direction+offset+1)%12
  elif a==3:rotation=(rotation+1)%4
  else:offset=(offset+1)%4
  history.append((a,rotation,offset));pa=(pa+1)%x["periods"][0];pb=(pb+1)%x["periods"][1]
 elif a==5:
  if pa or pb or not history:return None
  exchange=(tuple(shuttles),rotation,offset,len(history));shuttles.reverse();history=[]
 return tuple(shuttles),rotation,offset,pa,pb,tuple(history),exchange
def target(x):
 s=((2,9),0,0,0,0,(),None)
 for a in x["plan"]:s=advance(s,a,x);assert s is not None
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=GARDEN;f[8:32,7:29]=CLOUD;f[8:32,35:57]=FRAME
  for i,v in enumerate(g.shuttles):x=10+i*28;f[11+(v%8)*2:17+(v%8)*2,x:x+14]=RAIN-i
  f[37:40,8:11+g.pa*9]=CYCLEA;f[43:46,8:11+g.pb*9]=CYCLEB;f[49:52,8:11+g.rotation*11]=FRAME;f[55:58,8:11+g.offset*11]=EXCHANGE
  if g.bad:f[61:64,20:44]=BAD
  return f
class Q529(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self._reset();self.target=target(LEVELS[0]);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q529",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.shuttles=(2,9);self.rotation=self.offset=self.pa=self.pb=0;self.history=();self.exchange=None
 def on_set_level(self,l):self._reset();self.bad=False;self.target=target(LEVELS[self.level_index])
 def step(self):
  a=self.action.id.value;x=LEVELS[self.level_index]
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):
   s=advance((self.shuttles,self.rotation,self.offset,self.pa,self.pb,self.history,self.exchange),a,x)
   if s is None:self.bad=True;self.lose()
   else:self.shuttles,self.rotation,self.offset,self.pa,self.pb,self.history,self.exchange=s
  elif a==6:
   if (self.shuttles,self.rotation,self.offset,self.pa,self.pb,self.history,self.exchange)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
