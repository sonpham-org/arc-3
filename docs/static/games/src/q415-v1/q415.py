"""q415 Alloy Revision -- recalibrate a worn law expressed in a moving foundry frame."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,FOUNDRY,LANE,BILLET,WEAR,RULE,FRAME,REPAIR,BAD=7,10,9,14,12,5,11,6,15
LEVELS=[{"name":"Old Force","boundary":3,"mode":1,"plan":(1,2,5)},{"name":"Wear Lane","boundary":2,"mode":2,"plan":(2,1,4,5)},{"name":"Delayed Billet","boundary":2,"mode":3,"plan":(3,2,1,5)},{"name":"Rotated Law","boundary":3,"mode":2,"plan":(1,4,2,3,5)},{"name":"Translated Revision","boundary":2,"mode":1,"plan":(2,3,4,1,2,5)},{"name":"Alloy Revision","boundary":3,"mode":3,"plan":(3,1,4,2,3,1,5)}]
def advance(s,a,x):
 billets,wear,rotation,offset,delay=s;billets=list(billets)
 if a in (1,2,3):
  i=(a-1+rotation)%3;rule=1 if wear<x["boundary"] else x["mode"]
  if rule==1:billets[i]=(billets[i]+a+offset)%4
  elif rule==2:billets[i]=3-billets[i]
  else:delay=(delay+a+i+rotation+offset)%4
  wear+=1
 elif a==4:rotation=(rotation+1)%4;offset=(offset+1)%5
 elif a==5:billets=[(v+delay+rotation+offset)%4 for v in billets];delay=0
 return tuple(billets),wear,rotation,offset,delay
def target(x):
 s=((0,1,2),0,0,0,0)
 for a in x["plan"]:s=advance(s,a,x)
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=FOUNDRY;f[8:15,8:56]=LANE
  for i,v in enumerate(g.billets):x=9+i*18;f[20:37,x:x+12]=BILLET-i;f[24+v*3:29+v*3,x+3:x+9]=RULE
  f[42:45,8:11+min(g.wear,7)*6]=WEAR;f[49:52,8:11+g.delay*11]=REPAIR;f[54:57,8:11+g.rotation*11]=FRAME;f[58:60,8:11+g.offset*9]=FRAME
  if g.bad:f[61:64,20:44]=BAD
  return f
class Q415(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self._reset();self.target=target(LEVELS[0]);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q415",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.billets=(0,1,2);self.wear=self.rotation=self.offset=self.delay=0
 def on_set_level(self,l):self._reset();self.bad=False;self.target=target(LEVELS[self.level_index])
 def step(self):
  a=self.action.id.value;x=LEVELS[self.level_index]
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.billets,self.wear,self.rotation,self.offset,self.delay=advance((self.billets,self.wear,self.rotation,self.offset,self.delay),a,x)
  elif a==6:
   if (self.billets,self.wear,self.rotation,self.offset,self.delay)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
