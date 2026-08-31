"""a088 Foundation Shift -- move supports while keeping the center inside."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay

BG,YARD,GROUND,SUPPORT,STACK,CENTER,POLYGON,MOVE,MARGIN,BAD=0,8,9,12,14,10,11,13,6,15
LEVELS=[
 {"name":"Slide Support","seq":(1,)},{"name":"Select Tile","seq":(3,)},
 {"name":"Shift Right","seq":(2,3,1)},{"name":"Move Stack","seq":(1,3,2,4,1)},
 {"name":"Intermediate Balance","seq":(1,3,2,1,4,3,2)},{"name":"Foundation Shift","seq":(1,3,2,4,1,3,2,1,4,2)},
]
def advance(s,a):
 supports,cursor,center,target,unstable,moves,history,snapshot=s;sp=list(supports)
 if a==1:sp[cursor]=max(0,sp[cursor]-1);history=(history+(1,))[-8:]
 elif a==2:sp[cursor]=min(10,sp[cursor]+1);history=(history+(2,))[-8:]
 elif a==3:cursor=(cursor+1)%3;history=(history+(3,))[-8:]
 elif a==4:center=min(10,center+1);target=min(10,target+1);moves=(moves+1)%7;history=(history+(4,))[-8:]
 if a in (1,2,3,4):unstable=(unstable+int(not(min(sp)<=center<=max(sp))))%6
 elif a==5:snapshot=(tuple(sp),cursor,center,target,unstable,moves,history)
 return tuple(sp),cursor,center,target,unstable,moves,history,snapshot
for x in LEVELS:
 s=((2,4,6),0,4,6,0,0,(),None)
 for a in x["seq"]:s=advance(s,a)
 x["plan"]=x["seq"]+(5,);x["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=YARD;f[48:55,6:58]=GROUND
  lo,hi=min(g.supports),max(g.supports);f[43:47,8+lo*4:13+hi*4]=POLYGON
  for i,p in enumerate(g.supports):x=8+p*4;f[44:55,x:x+7]=SUPPORT;ifill=MOVE if i==g.cursor else SUPPORT;f[52:57,x:x+7]=ifill
  cx=10+g.center*4;f[17:44,cx:cx+10]=STACK;f[12:17,cx+3:cx+7]=CENTER
  f[8:11,8:8+g.moves*7]=MOVE
  for i in range(g.unstable):f[56:59,42+i*3:45+i*3]=BAD
  if g.bad:f[1:4,18:46]=BAD
  return f
class A088(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"];ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("a088",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.supports,self.cursor,self.center,self.target_pos,self.unstable,self.moves,self.history,self.snapshot=((2,4,6),0,4,6,0,0,(),None)
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.supports,self.cursor,self.center,self.target_pos,self.unstable,self.moves,self.history,self.snapshot=advance((self.supports,self.cursor,self.center,self.target_pos,self.unstable,self.moves,self.history,self.snapshot),a)
  elif a==6:
   if (self.supports,self.cursor,self.center,self.target_pos,self.unstable,self.moves,self.history,self.snapshot)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
