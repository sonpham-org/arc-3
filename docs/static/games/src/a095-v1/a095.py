"""a095 Plastic Trail -- combine elastic recovery with permanent yield."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay

BG,LAND,ROAD,LIGHT,HEAVY,DENT,RAMP,ROLLER,YIELD,BAD=7,8,9,10,14,12,13,11,6,15
LEVELS=[
 {"name":"Choose Load","seq":(1,)},{"name":"Roll Segment","seq":(2,)},
 {"name":"Light Recovery","seq":(2,4)},{"name":"Yield Threshold","seq":(1,2,3,2,4)},
 {"name":"Sculpt Ramp","seq":(1,2,3,2,4,3,2)},{"name":"Plastic Trail","seq":(2,1,2,3,4,2,3,1,2,4)},
]
def advance(s,a):
 heights,plastic,load,cursor,roller,yielded,history,snapshot=s;h=list(heights);p=list(plastic)
 if a==1:load=1+load%3;history=(history+(1,))[-8:]
 elif a==2:h[cursor]=max(-4,h[cursor]-load);p[cursor]=min(4,p[cursor]+int(load>=2));roller=cursor;history=(history+(2,))[-8:]
 elif a==3:cursor=(cursor+1)%8;history=(history+(3,))[-8:]
 elif a==4:
  for i in range(8):h[i]+=(0-h[i])//2 if p[i]==0 else 0
  yielded=sum(p);history=(history+(4,))[-8:]
 elif a==5:snapshot=(tuple(h),tuple(p),load,cursor,roller,yielded,history)
 return tuple(h),tuple(p),load,cursor,roller,yielded,history,snapshot
for x in LEVELS:
 s=((0,0,0,0,0,0,0,0),(0,0,0,0,0,0,0,0),1,0,0,0,(),None)
 for a in x["seq"]:s=advance(s,a)
 x["plan"]=x["seq"]+(5,);x["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=LAND
  for i,(v,p) in enumerate(zip(g.heights,g.plastic)):
   x=7+i*6;y=36-v*3;f[y:50,x:x+6]=DENT if p else ROAD
   if i==g.cursor:f[52:56,x:x+6]=YIELD
  x=7+g.roller*6;f[24:33,x:x+8]=HEAVY if g.load>=2 else LIGHT
  f[8:12,8:8+g.load*12]=ROLLER;f[14:18,8:8+min(8,g.yielded)*5]=RAMP
  if g.bad:f[1:4,18:46]=BAD
  return f
class A095(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"];ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("a095",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.heights,self.plastic,self.load,self.cursor,self.roller,self.yielded,self.history,self.snapshot=((0,0,0,0,0,0,0,0),(0,0,0,0,0,0,0,0),1,0,0,0,(),None)
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.heights,self.plastic,self.load,self.cursor,self.roller,self.yielded,self.history,self.snapshot=advance((self.heights,self.plastic,self.load,self.cursor,self.roller,self.yielded,self.history,self.snapshot),a)
  elif a==6:
   if (self.heights,self.plastic,self.load,self.cursor,self.roller,self.yielded,self.history,self.snapshot)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
