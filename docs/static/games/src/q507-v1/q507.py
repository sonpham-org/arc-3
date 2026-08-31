"""q507 Canopy Frame -- compose moving orchard frames through a capacity-limited store."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,ORCHARD,SHADE,GLIDER,FRAME,STORE,TRACE,GOAL,BAD=4,10,9,14,5,11,6,7,15
LEVELS=[{"name":"Local Seed","capacity":1,"plan":(1,4,5)},{"name":"Translated Terrace","capacity":1,"plan":(2,3,4,5)},{"name":"Two-Slot Crossing","capacity":2,"plan":(1,4,2,4,5,5)},{"name":"Narrow Store","capacity":1,"plan":(3,1,4,5,2)},{"name":"Ordered Exchange","capacity":2,"plan":(2,4,3,1,4,5,5)},{"name":"Canopy Frame","capacity":2,"plan":(1,3,4,2,4,5,3,5)}]
def advance(s,a,x):
 gliders,rotation,offset,store,history=s;gliders=list(gliders);store=list(store);history=list(history)
 if a in (1,2):
  if not gliders:return None
  i=(a-1+rotation)%len(gliders);gliders[i]=(gliders[i]+(1 if a==1 else -1)+offset)%5
 elif a==3:
  rotation=(rotation+1)%4
  if gliders:gliders=gliders[1:]+gliders[:1]
 elif a==4:
  if len(store)>=x["capacity"] or not gliders:return None
  offset=(offset+1)%5;item=gliders.pop(0);store.append((item,rotation,offset));history.append((1,len(store)))
 elif a==5:
  if not store:return None
  item,r,o=store.pop();gliders.append((item+rotation+r+offset+o)%5);history.append((2,len(store)))
 return tuple(gliders),rotation,offset,tuple(store),tuple(history)
def target(x):
 s=((0,2,4),0,0,(),())
 for a in x["plan"]:s=advance(s,a,x);assert s is not None
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;x=LEVELS[g.level_index];f[:,:]=BG;f[4:60,4:60]=ORCHARD;f[8:15,8:56]=SHADE
  for i,v in enumerate(g.gliders):px=8+i*17;f[20:35,px:px+13]=GLIDER-i;f[24+v*2:28+v*2,px+4:px+9]=TRACE
  for i,(_,r,o) in enumerate(g.store):f[39+i*6:44+i*6,10:22]=STORE;f[39+i*6:44+i*6,24:28+r*5]=FRAME
  f[51:54,8:11+g.rotation*11]=FRAME;f[55:58,8:11+len(g.store)*18]=STORE;f[58:60,48:56]=GOAL
  if g.bad:f[61:64,20:44]=BAD
  return f
class Q507(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self._reset();self.target=target(LEVELS[0]);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q507",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.gliders=(0,2,4);self.rotation=self.offset=0;self.store=();self.history=()
 def on_set_level(self,l):self._reset();self.bad=False;self.target=target(LEVELS[self.level_index])
 def step(self):
  a=self.action.id.value;x=LEVELS[self.level_index]
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):
   s=advance((self.gliders,self.rotation,self.offset,self.store,self.history),a,x)
   if s is None:self.bad=True;self.lose()
   else:self.gliders,self.rotation,self.offset,self.store,self.history=s
  elif a==6:
   if (self.gliders,self.rotation,self.offset,self.store,self.history)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
