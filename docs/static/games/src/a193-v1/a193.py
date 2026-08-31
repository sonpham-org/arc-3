"""a193 Hot Swap -- replace a live module through a synchronized bypass."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay

BG,FLOOR,OLD,NEW,BYPASS,FLOW,SYNC,CURSOR,LOST,DUPLICATE=2,8,12,14,10,4,5,13,6,9
BAD=15
LEVELS=[
 {"name":"Open Bypass","seq":(1,)},{"name":"Copy State","seq":(2,)},
 {"name":"Advance Line","seq":(3,1)},{"name":"Switch Module","seq":(1,2,3,4,2)},
 {"name":"No Lost Item","seq":(1,3,2,1,4,3,2)},{"name":"Hot Swap","seq":(1,2,3,1,4,2,3,1,4,3)},
]
def advance(s,a):
 bypass,synced,flow,active,lost,duplicates,history,snapshot=s
 if a==1:bypass=not bypass;history=(history+(1,))[-8:]
 elif a==2:synced=(synced+1)%4;history=(history+(2,))[-8:]
 elif a==3:flow=(flow+1)%8;lost+=int(not bypass and active==1);history=(history+(3,))[-8:]
 elif a==4:
  if bypass and synced==flow%4:active=1-active
  else:duplicates+=1
  history=(history+(4,))[-8:]
 elif a==5:snapshot=(bypass,synced,flow,active,lost,duplicates,history)
 return bypass,synced,flow,active,lost,duplicates,history,snapshot
for q in LEVELS:
 s=(False,0,0,0,0,0,(),None)
 for a in q["seq"]:s=advance(s,a)
 q["plan"]=q["seq"]+(5,);q["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[5:59,4:60]=FLOOR;f[22:42,9:23]=OLD if g.active==0 else NEW;f[22:42,41:55]=NEW if g.active==0 else OLD
  f[29:35,23:41]=FLOW;f[12:18,16:48]=BYPASS if g.bypass else FLOOR;f[9:12,16+g.synced*8:22+g.synced*8]=SYNC
  f[45:50,8+g.flow*6:13+g.flow*6]=CURSOR;f[53:57,8:8+min(6,g.lost)*6]=LOST;f[53:57,43:43+min(3,g.duplicates)*5]=DUPLICATE
  if g.bad:f[1:4,18:46]=BAD
  return f
class A193(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"];ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(q),name=q["name"]) for q in LEVELS];super().__init__("a193",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.bypass,self.synced,self.flow,self.active,self.lost,self.duplicates,self.history,self.snapshot=(False,0,0,0,0,0,(),None)
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.bypass,self.synced,self.flow,self.active,self.lost,self.duplicates,self.history,self.snapshot=advance((self.bypass,self.synced,self.flow,self.active,self.lost,self.duplicates,self.history,self.snapshot),a)
  elif a==6:
   if (self.bypass,self.synced,self.flow,self.active,self.lost,self.duplicates,self.history,self.snapshot)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
