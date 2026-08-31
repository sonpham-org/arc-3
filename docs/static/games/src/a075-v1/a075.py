"""a075 Cam Garden -- choose cam profiles for timed follower presses."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay

BG,GARDEN,SHAFT,CAM_A,CAM_B,CAM_C,FOLLOWER,FLOWER,PRESS,BAD=3,8,9,12,14,10,11,13,6,15
LEVELS=[
 {"name":"Select Cam","seq":(2,)},{"name":"Change Profile","seq":(1,)},
 {"name":"Rotate Shaft","seq":(1,3)},{"name":"Phase Press","seq":(2,1,3,4)},
 {"name":"Flower Pattern","seq":(1,3,2,1,3,4,3)},{"name":"Cam Garden","seq":(1,2,3,1,3,4,2,1,3,4)},
]
def advance(s,a):
 cams,phases,cursor,shaft,flowers,presses,history,snapshot=s;c=list(cams);p=list(phases);fl=list(flowers)
 if a==1:c[cursor]=(c[cursor]+1)%3;history=(history+(1,))[-8:]
 elif a==2:cursor=(cursor+1)%3;history=(history+(2,))[-8:]
 elif a==3:
  shaft=(shaft+1)%8
  for i in range(3):p[i]=(p[i]+1+c[i])%8;fl[i]=(fl[i]+int(p[i] in (0,c[i]+2)))%5
  history=(history+(3,))[-8:]
 elif a==4:presses=(presses+(tuple(fl),))[-5:];history=(history+(4,))[-8:]
 elif a==5:snapshot=(tuple(c),tuple(p),cursor,shaft,tuple(fl),presses,history)
 return tuple(c),tuple(p),cursor,shaft,tuple(fl),presses,history,snapshot
for x in LEVELS:
 s=((0,1,2),(0,2,4),0,0,(0,0,0),(),(),None)
 for a in x["seq"]:s=advance(s,a)
 x["plan"]=x["seq"]+(5,);x["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=GARDEN;f[19:25,7:57]=SHAFT
  cols=(CAM_A,CAM_B,CAM_C)
  for i,v in enumerate(g.cams):
   x=9+i*17;r=5+v*2;f[22-r:23+r,x:x+10]=cols[v]
   f[31:45,x+3:x+7]=FOLLOWER;f[45-g.flowers[i]*2:50,x:x+10]=FLOWER
   if i==g.cursor:f[10:14,x:x+10]=PRESS
  for i,_ in enumerate(g.presses):f[54:58,8+i*9:15+i*9]=PRESS
  if g.bad:f[1:4,18:46]=BAD
  return f
class A075(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"];ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("a075",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.cams,self.phases,self.cursor,self.shaft,self.flowers,self.presses,self.history,self.snapshot=((0,1,2),(0,2,4),0,0,(0,0,0),(),(),None)
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.cams,self.phases,self.cursor,self.shaft,self.flowers,self.presses,self.history,self.snapshot=advance((self.cams,self.phases,self.cursor,self.shaft,self.flowers,self.presses,self.history,self.snapshot),a)
  elif a==6:
   if (self.cams,self.phases,self.cursor,self.shaft,self.flowers,self.presses,self.history,self.snapshot)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
